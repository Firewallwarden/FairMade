"""Exact remaining sellable counts, safe filtering and current visibility."""

from datetime import UTC, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, event
from sqlalchemy.orm import Session

from fairmade.models import AccountRole, Order, PayPalCheckout, SellableInventory

PUBLIC = "/api/v1/marketplace/listings"


def detail(client, source):
    response = client.get(PUBLIC + "/" + source["listing"]["id"])
    assert response.status_code == 200, response.text
    return response.json()


def order(client, buyer, cart):
    response = client.post(
        "/api/v1/orders", headers={**buyer, "Idempotency-Key": str(uuid4())}, json=cart
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_exact_available_units_do_not_change_approved_payload(
    market_client, market_headers, buyer_headers, order_source, cart
):
    before = detail(market_client, order_source)
    assert before["availability"]["status"] == "available"
    assert before["availability"]["available_units"] == 10
    assert before["availability"]["selling_unit"] == "loaf"
    held = order(market_client, buyer_headers, cart)
    after = detail(market_client, order_source)
    assert after["availability"]["available_units"] == 8
    assert after["payload"] == before["payload"] and after["payload_hash"] == before["payload_hash"]
    assert after["published_revision"] == before["published_revision"]
    assert set(after["availability"]) == {
        "status",
        "available_units",
        "selling_unit",
        "basis",
        "notice",
    }
    assert "seller_recorded_stock" in after["availability"]["basis"]
    assert not {"on_hand", "reserved", "revision", "product_id", "buyer_account_id"} & set(
        after["availability"]
    )
    assert (
        market_client.post(
            "/api/v1/orders/" + held["id"] + "/cancel", headers=buyer_headers
        ).status_code
        == 200
    )
    assert detail(market_client, order_source)["availability"]["available_units"] == 10
    assert market_client.get(PUBLIC).headers["Cache-Control"] == "no-store"


def test_zero_and_unknown_are_distinct_and_filters_precede_pagination(
    market_client, listing_factory
):
    available = listing_factory("Available loaf", 7)
    empty = listing_factory("Empty loaf", 0)
    unknown = listing_factory("Unknown loaf", None)
    for status, source, units in (
        ("available", available, 7),
        ("unavailable", empty, 0),
        ("unknown", unknown, None),
    ):
        response = market_client.get(PUBLIC + "?availability=" + status + "&limit=1")
        assert response.status_code == 200
        items = response.json()["items"]
        assert [row["id"] for row in items] == [source["listing"]["id"]]
        assert items[0]["availability"]["status"] == status
        assert items[0]["availability"].get("available_units") == units
    assert market_client.get(PUBLIC + "?availability=available&offset=1").json()["items"] == []
    assert (
        market_client.get(PUBLIC + "?availability=available&q=Available").json()["items"][0]["id"]
        == available["listing"]["id"]
    )
    assert (
        market_client.get(PUBLIC + "?availability=available&location=Elsewhere").json()["items"]
        == []
    )


def test_approved_unit_controls_counts_not_private_product_edits(
    market_client, market_headers, order_source
):
    path = order_source["path"]
    assert (
        market_client.patch(
            path, headers=market_headers, json={"selling_unit": "dozen"}
        ).status_code
        == 200
    )
    assert detail(market_client, order_source)["availability"]["available_units"] == 10
    assert (
        market_client.put(
            path + "/inventory",
            headers=market_headers,
            json={
                "expected_revision": 1,
                "selling_unit": "loaf",
                "on_hand": 0,
            },
        ).status_code
        == 200
    )
    assert (
        market_client.put(
            path + "/inventory",
            headers=market_headers,
            json={
                "expected_revision": 2,
                "selling_unit": "dozen",
                "on_hand": 10,
            },
        ).status_code
        == 200
    )
    availability = detail(market_client, order_source)["availability"]
    assert availability["status"] == "unknown" and "available_units" not in availability
    assert availability["selling_unit"] == "loaf"
    assert market_client.get(PUBLIC + "?availability=available").json()["items"] == []


def test_all_held_units_are_unavailable_and_multiple_orders_sum_exactly(
    market_client, buyer_headers, order_source, cart
):
    first = order(market_client, buyer_headers, cart)
    order(market_client, buyer_headers, cart)
    assert detail(market_client, order_source)["availability"]["available_units"] == 6
    remaining_cart = {"items": [{**cart["items"][0], "quantity": 6}]}
    order(market_client, buyer_headers, remaining_cart)
    availability = detail(market_client, order_source)["availability"]
    assert availability["status"] == "unavailable" and availability["available_units"] == 0
    assert market_client.get(PUBLIC + "?availability=available").json()["items"] == []
    assert len(market_client.get(PUBLIC + "?availability=unavailable").json()["items"]) == 1
    market_client.post("/api/v1/orders/" + first["id"] + "/cancel", headers=buyer_headers)
    assert detail(market_client, order_source)["availability"]["available_units"] == 2


def test_nearby_filter_applies_before_candidate_guard_and_page(
    market_client, listing_factory, approved_storefront, monkeypatch
):
    from fairmade.discovery import repository

    listing_factory("Empty", 0)
    available = listing_factory("Available", 4)
    listing_factory("Unknown", None)
    monkeypatch.setattr(repository, "MAX_CANDIDATES", 1)
    search = {"origin": {"latitude": "0", "longitude": "0"}, "radius_km": "25", "limit": 1}
    assert market_client.post("/api/v1/discovery/listings", json=search).status_code == 409
    filtered = market_client.post(
        "/api/v1/discovery/listings", json={**search, "availability": "available"}
    )
    assert filtered.status_code == 200
    assert [row["listing"]["id"] for row in filtered.json()["items"]] == [
        available["listing"]["id"]
    ]


def test_expired_unpaid_holds_release_counts_without_writes(
    market_client, market_headers, buyer_headers, order_source, cart, monkeypatch
):
    held = order(market_client, buyer_headers, cart)
    with Session(market_client.app.state.engine) as db:
        after_expiry = db.get(Order, held["id"]).expires_at.replace(tzinfo=UTC) + timedelta(
            seconds=1
        )
    monkeypatch.setattr("fairmade.availability.query.utcnow", lambda: after_expiry)
    writes = []

    def inspect(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            writes.append(statement)

    event.listen(market_client.app.state.engine, "before_cursor_execute", inspect)
    try:
        assert detail(market_client, order_source)["availability"]["available_units"] == 10
    finally:
        event.remove(market_client.app.state.engine, "before_cursor_execute", inspect)
    assert writes == []
    with Session(market_client.app.state.engine) as db:
        assert db.get(Order, held["id"]).status == "pending_payment"


@pytest.mark.parametrize(
    "state,expected",
    [("ready", 10), ("creating", 10), ("failed", 10), ("capture_pending", 8), ("needs_review", 8)],
)
def test_checkout_recovery_holds_match_private_inventory(
    paypal_client,
    market_headers,
    order_source,
    unpaid_order,
    checkout,
    state,
    expected,
    monkeypatch,
):
    with Session(paypal_client.app.state.engine) as db, db.begin():
        after_expiry = db.get(Order, unpaid_order["id"]).expires_at.replace(tzinfo=UTC) + timedelta(
            seconds=1
        )
        db.get(PayPalCheckout, unpaid_order["id"]).state = state
    monkeypatch.setattr("fairmade.availability.query.utcnow", lambda: after_expiry)
    monkeypatch.setattr("fairmade.inventory.service.utcnow", lambda: after_expiry)
    public = detail(paypal_client, order_source)["availability"]["available_units"]
    private = paypal_client.get(order_source["path"] + "/inventory", headers=market_headers).json()
    assert public == private["available"] == expected


def test_verified_capture_does_not_double_subtract_held_stock(
    paypal_client, fake_gateway, buyer_headers, order_source, checkout, checkout_path
):
    assert detail(paypal_client, order_source)["availability"]["available_units"] == 8
    fake_gateway.approve(checkout["provider_order_id"])
    captured = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert captured.status_code == 200 and captured.json()["state"] == "completed"
    assert detail(paypal_client, order_source)["availability"]["available_units"] == 8


def test_impossible_negative_remaining_is_unknown_not_a_fabricated_zero(
    market_client, buyer_headers, order_source, cart
):
    order(market_client, buyer_headers, cart)
    # Simulate inconsistent legacy/operator data, outside the guarded inventory API.
    with Session(market_client.app.state.engine) as db, db.begin():
        db.get(SellableInventory, order_source["product"]["id"]).on_hand = 0
    availability = detail(market_client, order_source)["availability"]
    assert availability["status"] == "unknown" and "available_units" not in availability


def test_storefront_nearby_and_favorites_share_exact_counts_and_filters(
    market_client, market_headers, buyer_headers, order_source, cart, approved_storefront
):
    order(market_client, buyer_headers, cart)
    profile_id = approved_storefront["id"]
    path = "/api/v1/storefronts/" + profile_id + "/listings"
    listing_id = order_source["listing"]["id"]
    expected = detail(market_client, order_source)["availability"]
    storefront = market_client.get(path + "?availability=available&limit=1")
    assert storefront.json()["items"][0]["availability"] == expected
    assert market_client.get(path + "?availability=unavailable").json()["items"] == []
    search = {"origin": {"latitude": "0", "longitude": "0"}, "radius_km": "25"}
    nearby = market_client.post(
        "/api/v1/discovery/listings", json={**search, "availability": "available", "limit": 1}
    )
    assert nearby.status_code == 200, nearby.text
    assert nearby.json()["items"][0]["listing"]["availability"] == expected
    assert (
        market_client.post(
            "/api/v1/discovery/listings", json={**search, "availability": "unavailable"}
        ).json()["items"]
        == []
    )
    saved = market_client.post(
        "/api/v1/favorites", headers=buyer_headers, json={"listing_id": listing_id}
    )
    assert saved.status_code == 201 and saved.json()["listing"]["availability"] == expected
    assert (
        market_client.get("/api/v1/favorites", headers=buyer_headers).json()["items"][0]["listing"][
            "availability"
        ]
        == expected
    )
    market_client.post(order_source["path"] + "/listing/deactivate", headers=market_headers)
    assert market_client.get(PUBLIC + "/" + listing_id).status_code == 404
    assert market_client.get(path).json()["items"] == []
    hidden = market_client.get("/api/v1/favorites", headers=buyer_headers).json()["items"][0]
    assert hidden["listing"] is None and not hidden["listing_visible"]


def test_unit_counts_are_hidden_with_revoked_seller_access(market_client, order_source):
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
    assert market_client.get(PUBLIC).json()["items"] == []
    assert market_client.get(PUBLIC + "/" + order_source["listing"]["id"]).status_code == 404


def test_catalog_filter_queries_are_bounded_and_invalid_filters_rejected(
    market_client, listing_factory, approved_storefront
):
    listing_factory("First", 3)
    listing_factory("Second", 4)
    statements = []

    def inspect(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(market_client.app.state.engine, "before_cursor_execute", inspect)
    try:
        response = market_client.get(PUBLIC + "?availability=available&limit=2")
    finally:
        event.remove(market_client.app.state.engine, "before_cursor_execute", inspect)
    assert response.status_code == 200 and len(response.json()["items"]) == 2
    assert len(statements) == 1
    assert market_client.get(PUBLIC + "?availability=invalid").status_code == 422
    assert (
        market_client.get(
            "/api/v1/storefronts/" + approved_storefront["id"] + "/listings?availability=invalid"
        ).status_code
        == 422
    )
    assert (
        market_client.post(
            "/api/v1/discovery/listings",
            json={
                "origin": {"latitude": "0", "longitude": "0"},
                "radius_km": "25",
                "availability": "invalid",
            },
        ).status_code
        == 422
    )
