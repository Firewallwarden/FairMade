"""Required new publication data, exact approval and legacy visibility."""

import hashlib
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import MarketplaceListing

PUBLIC = "/api/v1/marketplace/listings"


def approval(client, headers, path):
    preview = client.get(path + "/preview", headers=headers)
    assert preview.status_code == 200, preview.text
    value = preview.json()
    return {
        "expected_revision": value["revision"],
        "preview_hash": value["preview_hash"],
        "approved": True,
    }


def activate(client, headers, path):
    return client.post(path + "/activate", headers=headers, json=approval(client, headers, path))


def legacy_snapshot(client, headers, path, listing_id):
    """Represent an approved pre-feature listing without bypassing new API validation."""
    assert activate(client, headers, path).status_code == 200
    with Session(client.app.state.engine) as db, db.begin():
        listing = db.get(MarketplaceListing, listing_id)
        content = dict(listing.content)
        content.pop("selling_quantity", None)
        payload = deepcopy(listing.public_payload)
        payload.pop("selling_quantity", None)
        payload.pop("unit_price", None)
        payload["notices"] = [
            "Listing and location information are seller-reported and unverified.",
            "A listing does not confirm stock, delivery, fulfillment, or payment availability.",
        ]
        listing.content = content
        listing.public_payload = payload
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        listing.payload_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return payload, listing.payload_hash


def test_drafts_remain_saveable_but_new_publication_requires_explicit_quantity(
    market_client,
    market_headers,
    market_record,
    listing_content,
):
    path = market_record["path"] + "/listing"
    draft = {key: value for key, value in listing_content.items() if key != "selling_quantity"}
    created = market_client.post(path, headers=market_headers, json=draft)
    assert created.status_code == 201
    preview = market_client.get(path + "/preview", headers=market_headers).json()
    assert preview["publication_blockers"] == ["SELLING_QUANTITY_REQUIRED"]
    assert "unit_price" not in preview["payload"] and "selling_quantity" not in preview["payload"]
    response = activate(market_client, market_headers, path)
    assert (
        response.status_code == 409
        and response.json()["detail"]["code"] == "SELLING_QUANTITY_REQUIRED"
    )
    assert response.headers["Cache-Control"] == "no-store"
    assert market_client.get(PUBLIC).json()["items"] == []
    with Session(market_client.app.state.engine) as db:
        row = db.get(MarketplaceListing, created.json()["id"])
        assert (
            row.state == "draft" and row.published_revision is None and row.public_payload is None
        )


def test_seller_approves_quantity_and_price_together_and_later_edits_stay_private(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
):
    path = market_record["path"] + "/listing"
    update = {
        **listing_content,
        "expected_revision": 1,
        "selling_quantity": {"value": "500", "unit": "g"},
    }
    assert market_client.put(path, headers=market_headers, json=update).status_code == 200
    first_approval = approval(market_client, market_headers, path)
    assert (
        market_client.post(
            path + "/activate", headers=market_headers, json=first_approval
        ).status_code
        == 200
    )
    first = market_client.get(PUBLIC + "/" + listing["id"]).json()
    assert first["payload"]["selling_quantity"] == {"value": "500", "unit": "g"}
    unit = first["payload"]["unit_price"]
    assert unit["amount"] == "34.000000" and unit["reference_unit"] == "kg"
    assert (
        unit["basis"] == "seller_reported_unverified"
        and first["payload"]["price"]["amount"] == "17.00"
    )
    assert "PRIVATE_MARKET" not in json.dumps(first)
    changed = {**update, "expected_revision": 2, "selling_quantity": {"value": "250", "unit": "g"}}
    assert market_client.put(path, headers=market_headers, json=changed).status_code == 200
    assert market_client.get(PUBLIC + "/" + listing["id"]).json() == first
    stale = market_client.post(path + "/activate", headers=market_headers, json=first_approval)
    assert stale.status_code == 409
    assert activate(market_client, market_headers, path).status_code == 200
    current = market_client.get(PUBLIC + "/" + listing["id"]).json()
    assert current["payload"]["unit_price"]["amount"] == "68.000000"
    assert current["payload_hash"] != first["payload_hash"]
    # Product edits cannot reinterpret a quantity attached to the approved Passport.
    market_client.patch(market_record["path"], headers=market_headers, json={"selling_unit": "box"})
    assert market_client.get(PUBLIC + "/" + listing["id"]).json() == current


def test_legacy_publication_hash_visibility_and_exact_activation_retries_are_preserved(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
):
    path = market_record["path"] + "/listing"
    payload, old_hash = legacy_snapshot(market_client, market_headers, path, listing["id"])
    detail = market_client.get(PUBLIC + "/" + listing["id"])
    assert detail.status_code == 200 and detail.json()["payload"] == payload
    assert detail.json()["payload_hash"] == old_hash
    page = market_client.get(PUBLIC).json()["items"]
    assert page[0]["payload"] == payload and page[0]["payload_hash"] == old_hash
    before = detail.json()
    assert activate(market_client, market_headers, path).status_code == 200
    assert market_client.get(PUBLIC + "/" + listing["id"]).json() == before
    # A new private revision remains invisible until it meets the new requirement.
    draft = {
        **listing_content,
        "expected_revision": 1,
        "summary": "Edited old listing",
        "selling_quantity": None,
    }
    assert market_client.put(path, headers=market_headers, json=draft).status_code == 200
    preview = market_client.get(path + "/preview", headers=market_headers).json()
    assert preview["publication_blockers"] == ["SELLING_QUANTITY_REQUIRED"]
    assert activate(market_client, market_headers, path).status_code == 409
    assert market_client.get(PUBLIC + "/" + listing["id"]).json() == before
    draft.update(expected_revision=2, selling_quantity={"value": "1", "unit": "loaf"})
    assert market_client.put(path, headers=market_headers, json=draft).status_code == 200
    assert activate(market_client, market_headers, path).status_code == 200
    assert (
        market_client.get(PUBLIC + "/" + listing["id"]).json()["payload"]["unit_price"]["amount"]
        == "17.000000"
    )


def test_legacy_reactivation_requires_quantity_but_checkout_uses_original_selling_unit_price(
    market_client,
    market_headers,
    order_source,
    buyer_headers,
    cart,
):
    path = order_source["path"] + "/listing"
    listing_id = order_source["listing"]["id"]
    legacy_snapshot(market_client, market_headers, path, listing_id)
    order = market_client.post(
        "/api/v1/orders", headers={**buyer_headers, "Idempotency-Key": str(uuid4())}, json=cart
    )
    assert order.status_code == 201, order.text
    assert order.json()["snapshot"]["subtotal"]["amount"] == "34.00"
    assert market_client.post(path + "/deactivate", headers=market_headers).status_code == 204
    blocked = activate(market_client, market_headers, path)
    assert (
        blocked.status_code == 409
        and blocked.json()["detail"]["code"] == "SELLING_QUANTITY_REQUIRED"
    )
    assert market_client.get(PUBLIC + "/" + listing_id).status_code == 404


@pytest.mark.parametrize(
    "quantity",
    [
        {"value": 500, "unit": "g"},
        {"value": "0", "unit": "kg"},
        {"value": "NaN", "unit": "l"},
        {"value": "1.5", "unit": "item"},
        {"value": "1", "unit": "lb"},
        {"value": "1"},
        {"value": "1", "unit": "g", "private": "PRIVATE_RAW_INPUT"},
    ],
)
def test_invalid_quantity_input_is_redacted(
    market_client, market_headers, market_record, listing_content, quantity
):
    response = market_client.post(
        market_record["path"] + "/listing",
        headers=market_headers,
        json={
            **listing_content,
            "selling_quantity": quantity,
        },
    )
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_RAW_INPUT" not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_named_units_follow_approved_product_type(market_client, market_headers, market_source):
    source = market_source(product_type="eggs")
    path = source["path"] + "/listing"
    body = {
        "passport_publication_id": source["publication"]["id"],
        "seller_display_name": "Example farm",
        "selling_quantity": {"value": "1", "unit": "loaf"},
    }
    rejected = market_client.post(path, headers=market_headers, json=body)
    assert (
        rejected.status_code == 409
        and rejected.json()["detail"]["code"] == "SELLING_QUANTITY_MISMATCH"
    )
    body["selling_quantity"] = {"value": "1", "unit": "dozen"}
    created = market_client.post(path, headers=market_headers, json=body)
    assert created.status_code == 201
    assert activate(market_client, market_headers, path).status_code == 200
    current = market_client.get(PUBLIC + "/" + created.json()["id"]).json()
    assert current["payload"]["unit_price"]["reference_unit"] == "egg"


def test_quantity_publication_rolls_back_with_approval_and_survives_restart(
    market_client,
    market_headers,
    market_record,
    listing,
    market_url,
):
    path = market_record["path"] + "/listing"
    checked = approval(market_client, market_headers, path)

    def fail(db):
        if any(isinstance(record, MarketplaceListing) for record in db.dirty):
            raise RuntimeError("Synthetic quantity publication failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert (
                client.post(path + "/activate", headers=market_headers, json=checked).status_code
                == 500
            )
    finally:
        event.remove(Session, "before_commit", fail)
    assert market_client.get(PUBLIC).json()["items"] == []
    assert (
        market_client.post(path + "/activate", headers=market_headers, json=checked).status_code
        == 200
    )
    expected = market_client.get(PUBLIC + "/" + listing["id"]).json()
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(PUBLIC + "/" + listing["id"]).json() == expected


def test_catalog_storefront_discovery_and_saved_products_share_approved_quantity(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
    buyer_headers,
):
    path = market_record["path"] + "/listing"
    response = market_client.put(
        path,
        headers=market_headers,
        json={
            **listing_content,
            "expected_revision": 1,
            "selling_quantity": {"value": "500", "unit": "g"},
        },
    )
    assert response.status_code == 200
    assert activate(market_client, market_headers, path).status_code == 200
    expected = market_client.get(PUBLIC + "/" + listing["id"]).json()["payload"]
    favorite = market_client.post(
        "/api/v1/favorites", headers=buyer_headers, json={"listing_id": listing["id"]}
    )
    assert favorite.status_code == 201
    payloads = [
        favorite.json()["listing"]["payload"],
        market_client.get(PUBLIC).json()["items"][0]["payload"],
    ]
    base = "/api/v1/seller/storefronts"
    profile = market_client.post(
        base,
        headers=market_headers,
        json={
            "display_name": "Example bakery",
            "approximate_area": {"label": "Example area", "latitude": "0.00", "longitude": "0.00"},
        },
    ).json()
    preview = market_client.get(
        base + "/" + profile["id"] + "/preview", headers=market_headers
    ).json()
    published = market_client.post(
        base + "/" + profile["id"] + "/publish",
        headers=market_headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    )
    assert published.status_code == 200
    storefront = market_client.get("/api/v1/storefronts/" + profile["id"] + "/listings").json()
    payloads.append(storefront["items"][0]["payload"])
    nearby = market_client.post(
        "/api/v1/discovery/listings",
        json={
            "origin": {"latitude": "0", "longitude": "0"},
            "radius_km": "10.0",
        },
    )
    assert nearby.status_code == 200, nearby.text
    payloads.append(nearby.json()["items"][0]["listing"]["payload"])
    for payload in payloads:
        assert payload["selling_quantity"] == expected["selling_quantity"]
        assert payload["unit_price"] == expected["unit_price"]


def test_normalized_display_price_never_replaces_checkout_selling_unit_price(
    market_client,
    market_headers,
    order_source,
    listing_content,
    buyer_headers,
    cart,
):
    path = order_source["path"] + "/listing"
    changed = market_client.put(
        path,
        headers=market_headers,
        json={
            **listing_content,
            "expected_revision": 1,
            "selling_quantity": {"value": "500", "unit": "g"},
        },
    )
    assert changed.status_code == 200
    assert activate(market_client, market_headers, path).status_code == 200
    cart["items"][0]["expected_listing_revision"] = 2
    response = market_client.post(
        "/api/v1/orders",
        headers={
            **buyer_headers,
            "Idempotency-Key": str(uuid4()),
        },
        json=cart,
    )
    assert response.status_code == 201, response.text
    snapshot = response.json()["snapshot"]
    line = snapshot["items"][0]
    assert line["listing"]["unit_price"]["amount"] == "34.000000"
    assert line["unit_price"]["amount"] == "17.00"
    assert snapshot["subtotal"]["amount"] == "34.00"
