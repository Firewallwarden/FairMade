"""Catalog privacy, approval lifecycle, authorization, search and persistence."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AccountRole, MarketplaceListing, Product

PUBLIC = "/api/v1/marketplace/listings"


def approval(client, headers, path):
    result = client.get(path + "/preview", headers=headers)
    assert result.status_code == 200, result.text
    preview = result.json()
    return {
        "expected_revision": preview["revision"],
        "preview_hash": preview["preview_hash"],
        "approved": True,
    }


def activate(client, headers, path):
    return client.post(path + "/activate", headers=headers, json=approval(client, headers, path))


def test_listing_requires_exact_approval_and_only_exposes_public_fields(
    market_client,
    market_headers,
    market_record,
    listing,
):
    path = market_record["path"] + "/listing"
    assert market_client.get(PUBLIC).json()["items"] == []
    assert market_client.get(PUBLIC + "/" + listing["id"]).status_code == 404
    preview = market_client.get(path + "/preview", headers=market_headers).json()
    response = activate(market_client, market_headers, path)
    assert response.status_code == 200 and response.json()["state"] == "active"
    public = market_client.get(PUBLIC + "/" + listing["id"])
    assert public.status_code == 200
    result = public.json()
    assert result["payload"] == preview["payload"]
    assert result["payload_hash"] == preview["preview_hash"]
    assert result["passport"]["payload"] == market_record["publication"]["payload"]
    assert result["payload"]["price"] == {"currency": "USD", "amount": "17.00"}
    assert result["payload"]["product"]["title"] == "Public loaf"
    assert result["payload"]["seller_display_name"] == "Example bakery"
    assert set(result) == {
        "id",
        "published_revision",
        "published_at",
        "payload_hash",
        "payload",
        "passport",
    }
    encoded = json.dumps(result)
    assert "PRIVATE_MARKET_" not in encoded and "@example.com" not in encoded
    for private_id in (
        market_record["product"]["id"],
        market_record["analysis"]["id"],
        market_record["review"]["id"],
    ):
        assert private_id not in encoded
    assert "costs" not in result["passport"]["payload"]
    assert public.headers["Cache-Control"] == "no-store"
    assert market_client.get(PUBLIC).headers["Cache-Control"] == "no-store"
    with Session(market_client.app.state.engine) as db:
        stored = db.get(MarketplaceListing, listing["id"])
        assert stored.price_minor == 1700
        assert stored.approved_by_account_id == db.get(Product, stored.product_id).account_id
        assert stored.published_publication_id == market_record["publication"]["id"]


def test_duplicate_listing_returns_conflict(
    market_client, market_headers, market_record, listing, listing_content
):
    response = market_client.post(
        market_record["path"] + "/listing",
        headers=market_headers,
        json=listing_content,
    )
    assert response.status_code == 409 and response.json()["detail"]["code"] == "LISTING_EXISTS"


def test_private_edits_do_not_change_active_snapshot_or_search(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
):
    path = market_record["path"] + "/listing"
    assert activate(market_client, market_headers, path).status_code == 200
    previous = market_client.get(PUBLIC + "/" + listing["id"]).json()
    edited = market_client.put(
        path,
        headers=market_headers,
        json={
            **listing_content,
            "expected_revision": 1,
            "seller_display_name": "New bakery",
            "location": "Newtown",
        },
    )
    assert edited.status_code == 200 and edited.json()["revision"] == 2
    assert edited.json()["published_revision"] == 1
    assert market_client.get(PUBLIC + "/" + listing["id"]).json() == previous
    assert market_client.get(PUBLIC, params={"q": "New bakery"}).json()["items"] == []
    assert len(market_client.get(PUBLIC, params={"location": "Exampletown"}).json()["items"]) == 1
    assert activate(market_client, market_headers, path).status_code == 200
    current = market_client.get(PUBLIC + "/" + listing["id"]).json()
    assert current["published_revision"] == 2
    assert current["payload"]["seller_display_name"] == "New bakery"
    assert market_client.get(PUBLIC, params={"location": "Exampletown"}).json()["items"] == []


def test_stale_revisions_and_bad_hashes_are_rejected(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
):
    path = market_record["path"] + "/listing"
    body = approval(market_client, market_headers, path)
    bad = market_client.post(
        path + "/activate", headers=market_headers, json={**body, "preview_hash": "0" * 64}
    )
    assert bad.status_code == 409 and bad.json()["detail"]["code"] == "PREVIEW_MISMATCH"
    changed = market_client.put(
        path,
        headers=market_headers,
        json={**listing_content, "expected_revision": 1, "summary": "Edited"},
    )
    assert changed.status_code == 200
    assert (
        market_client.post(path + "/activate", headers=market_headers, json=body).status_code == 409
    )
    assert (
        market_client.put(
            path, headers=market_headers, json={**listing_content, "expected_revision": 1}
        ).status_code
        == 409
    )
    assert market_client.get(PUBLIC).json()["items"] == []


def test_activation_retry_and_deactivation_invalidates_earlier_approval(
    market_client,
    market_headers,
    market_record,
    listing,
):
    path = market_record["path"] + "/listing"
    body = approval(market_client, market_headers, path)
    first = market_client.post(path + "/activate", headers=market_headers, json=body)
    assert first.status_code == 200
    original = market_client.get(PUBLIC + "/" + listing["id"]).json()
    assert (
        market_client.post(path + "/activate", headers=market_headers, json=body).status_code == 200
    )
    assert market_client.get(PUBLIC + "/" + listing["id"]).json() == original
    assert market_client.post(path + "/deactivate", headers=market_headers).status_code == 204
    assert market_client.post(path + "/deactivate", headers=market_headers).status_code == 204
    assert market_client.get(PUBLIC).json()["items"] == []
    assert market_client.get(PUBLIC + "/" + listing["id"]).status_code == 404
    assert (
        market_client.post(path + "/activate", headers=market_headers, json=body).status_code == 409
    )
    assert activate(market_client, market_headers, path).status_code == 200
    assert market_client.get(PUBLIC + "/" + listing["id"]).status_code == 200


@pytest.mark.parametrize("change", ["withdraw", "supersede", "seller_role"])
def test_passport_or_role_visibility_changes_hide_catalog_immediately(
    market_client,
    market_headers,
    market_record,
    listing,
    change,
):
    path = market_record["path"] + "/listing"
    assert activate(market_client, market_headers, path).status_code == 200
    if change == "withdraw":
        url = (
            market_record["draft_url"]
            + "/publications/"
            + market_record["publication"]["id"]
            + "/withdraw"
        )
        assert market_client.post(url, headers=market_headers).status_code == 204
    elif change == "supersede":
        assert (
            market_client.put(
                market_record["draft_url"],
                headers=market_headers,
                json={
                    **market_record["passport_content"],
                    "expected_revision": 1,
                    "price": "19.25",
                },
            ).status_code
            == 200
        )
        preview = market_client.get(
            market_record["draft_url"] + "/preview", headers=market_headers
        ).json()
        publication = market_client.post(
            market_record["draft_url"] + "/publish",
            headers=market_headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        )
        assert publication.status_code == 201
    else:
        with Session(market_client.app.state.engine) as db, db.begin():
            db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
    assert market_client.get(PUBLIC).json()["items"] == []
    hidden = market_client.get(PUBLIC + "/" + listing["id"])
    assert hidden.status_code == 404 and hidden.headers["Cache-Control"] == "no-store"


def test_new_passport_requires_new_listing_approval(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
):
    path = market_record["path"] + "/listing"
    assert activate(market_client, market_headers, path).status_code == 200
    old_approval = approval(market_client, market_headers, path)
    assert (
        market_client.put(
            market_record["draft_url"],
            headers=market_headers,
            json={**market_record["passport_content"], "expected_revision": 1, "price": "19.25"},
        ).status_code
        == 200
    )
    p = market_client.get(market_record["draft_url"] + "/preview", headers=market_headers).json()
    publication = market_client.post(
        market_record["draft_url"] + "/publish",
        headers=market_headers,
        json={
            "expected_revision": p["revision"],
            "preview_hash": p["preview_hash"],
            "approved": True,
        },
    ).json()
    assert (
        market_client.post(
            path + "/activate", headers=market_headers, json=old_approval
        ).status_code
        == 404
    )
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={
                **listing_content,
                "expected_revision": 1,
                "passport_publication_id": publication["id"],
            },
        ).status_code
        == 200
    )
    assert market_client.get(PUBLIC).json()["items"] == []
    assert activate(market_client, market_headers, path).status_code == 200
    result = market_client.get(PUBLIC + "/" + listing["id"]).json()
    assert result["payload"]["price"]["amount"] == "19.25"
    assert result["passport"]["id"] == publication["id"]


@pytest.mark.parametrize(
    "method,suffix",
    [
        ("post", ""),
        ("get", ""),
        ("put", ""),
        ("get", "/preview"),
        ("post", "/activate"),
        ("post", "/deactivate"),
    ],
)
def test_private_routes_require_login(market_client, market_record, method, suffix):
    url = market_record["path"] + "/listing" + suffix
    if method in ("post", "put"):
        response = getattr(market_client, method)(url, json={})
    else:
        response = market_client.get(url)
    assert response.status_code == 401


@pytest.mark.parametrize("roles,pending", [((), False), ((), True), (("admin",), False)])
def test_buyer_pending_and_admin_accounts_cannot_manage(
    market_client,
    market_account,
    market_record,
    listing_content,
    roles,
    pending,
):
    headers = market_account("another-account@example.com", roles=roles)
    if pending:
        assert (
            market_client.post("/api/v1/seller-applications", headers=headers, json={}).status_code
            == 201
        )
    path = market_record["path"] + "/listing"
    requests = [
        ("get", "", None),
        ("get", "/preview", None),
        ("post", "", listing_content),
        ("put", "", {**listing_content, "expected_revision": 1}),
        ("post", "/activate", {"expected_revision": 1, "preview_hash": "0" * 64, "approved": True}),
        ("post", "/deactivate", None),
    ]
    for method, suffix, body in requests:
        response = market_client.request(method, path + suffix, headers=headers, json=body)
        assert response.status_code == 403
    assert market_client.get(PUBLIC, headers=headers).status_code == 200


def test_other_sellers_cannot_manage_or_link_private_products(
    market_client,
    market_account,
    market_headers,
    market_record,
    market_source,
    listing,
    listing_content,
):
    other = market_account("another-seller@example.com")
    path = market_record["path"] + "/listing"
    for method, suffix in [("get", ""), ("get", "/preview"), ("post", "/deactivate")]:
        response = getattr(market_client, method)(path + suffix, headers=other)
        assert response.status_code == 404
    for method, suffix, body in [
        ("post", "", listing_content),
        ("put", "", {**listing_content, "expected_revision": 1}),
        ("post", "/activate", approval(market_client, market_headers, path)),
    ]:
        assert (
            market_client.request(
                method,
                path + suffix,
                headers=other,
                json=body,
            ).status_code
            == 404
        )
    source = market_source(headers=other)
    response = market_client.post(
        source["path"] + "/listing",
        headers=other,
        json=listing_content,
    )
    assert response.status_code == 404
    another = market_source()
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={
                **listing_content,
                "expected_revision": 1,
                "passport_publication_id": another["publication"]["id"],
            },
        ).status_code
        == 404
    )
    assert (
        market_client.post(
            another["path"] + "/listing",
            headers=market_headers,
            json={**listing_content, "passport_publication_id": str(uuid4())},
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"price": "0.01"},
        {"price_minor": 1},
        {"state": "active"},
        {"product_type": "eggs"},
        {"account_id": str(uuid4())},
        {"seller_display_name": " "},
        {"location": "x" * 201},
        {"summary": "x" * 1001},
    ],
)
def test_listing_rejects_client_price_and_invalid_content(
    market_client,
    market_headers,
    market_record,
    listing_content,
    extra,
):
    response = market_client.post(
        market_record["path"] + "/listing",
        headers=market_headers,
        json={**listing_content, **extra},
    )
    assert response.status_code == 422


def test_search_filters_literal_wildcards_pagination_and_stable_order(
    market_client,
    market_headers,
    market_source,
):
    records = [
        market_source(title="100% bread_1", price="10"),
        market_source(title="Another loaf", price="20"),
        market_source(title="Example eggs", product_type="eggs", price="3.50"),
    ]
    ids = []
    for i, record in enumerate(records):
        path = record["path"] + "/listing"
        response = market_client.post(
            path,
            headers=market_headers,
            json={
                "passport_publication_id": record["publication"]["id"],
                "seller_display_name": "Example Bakery" if i < 2 else "Example Farm",
                "location": "Springfield" if i < 2 else "Elsewhere",
            },
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])
        assert activate(market_client, market_headers, path).status_code == 200

    def search(**params):
        response = market_client.get(PUBLIC, params=params)
        assert response.status_code == 200
        return [item["id"] for item in response.json()["items"]]

    assert search() == list(reversed(ids))
    assert search(q="%") == [ids[0]]
    assert search(q="_1") == [ids[0]]
    assert search(q="EXAMPLE BAKERY") == list(reversed(ids[:2]))
    assert search(product_type="eggs") == [ids[2]]
    assert search(location="springFIELD") == list(reversed(ids[:2]))
    assert search(product_type="sourdough", q="Another", location="Springfield") == [ids[1]]
    assert search(limit=1, offset=1) == [ids[1]]
    assert search(offset=100) == []
    for params in (
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"product_type": "invalid"},
        {"q": "x" * 201},
    ):
        assert market_client.get(PUBLIC, params=params).status_code == 422


def test_concurrent_approval_retries_are_stable(
    market_client, market_url, market_headers, market_record, listing
):
    path = market_record["path"] + "/listing"
    body = approval(market_client, market_headers, path)
    barrier = Barrier(2)
    # Initialize schemas before concurrent requests, as a running server does.
    applications = [create_app(market_url) for _ in range(2)]

    def submit(index):
        with TestClient(applications[index]) as client:
            barrier.wait(timeout=10)
            return client.post(path + "/activate", headers=market_headers, json=body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert len(market_client.get(PUBLIC).json()["items"]) == 1


@pytest.mark.parametrize("operation", ["create", "replace", "activate", "deactivate"])
def test_failed_transactions_preserve_previous_public_snapshot(
    market_client,
    market_url,
    market_headers,
    market_record,
    listing_content,
    operation,
):
    path = market_record["path"] + "/listing"
    if operation != "create":
        assert (
            market_client.post(path, headers=market_headers, json=listing_content).status_code
            == 201
        )
        assert activate(market_client, market_headers, path).status_code == 200
    before = market_client.get(PUBLIC).json()
    if operation == "activate":
        assert (
            market_client.put(
                path,
                headers=market_headers,
                json={**listing_content, "expected_revision": 1, "summary": "Changed but private"},
            ).status_code
            == 200
        )
    body = approval(market_client, market_headers, path) if operation == "activate" else None

    def fail(_db):
        raise RuntimeError("Synthetic listing storage failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            if operation == "create":
                response = client.post(path, headers=market_headers, json=listing_content)
            elif operation == "replace":
                response = client.put(
                    path,
                    headers=market_headers,
                    json={**listing_content, "expected_revision": 1, "summary": "Never committed"},
                )
            elif operation == "activate":
                response = client.post(path + "/activate", headers=market_headers, json=body)
            else:
                response = client.post(path + "/deactivate", headers=market_headers)
            assert response.status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert market_client.get(PUBLIC).json() == before


def test_restart_migration_and_contract(
    market_client, market_url, market_headers, market_record, listing
):
    path = market_record["path"] + "/listing"
    assert activate(market_client, market_headers, path).status_code == 200
    before = market_client.get(PUBLIC + "/" + listing["id"]).json()
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(PUBLIC + "/" + listing["id"]).json() == before
    with market_client.app.state.engine.connect() as connection:
        private_before = connection.execute(
            text("SELECT * FROM passport_publications ORDER BY id")
        ).all()
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.check(config)
    command.downgrade(config, "0006")
    command.upgrade(config, "head")
    with market_client.app.state.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT * FROM passport_publications ORDER BY id")).all()
            == private_before
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    assert market_client.get(PUBLIC).json()["items"] == []
    schema = market_client.get("/openapi.json").json()
    for suffix in ("", "/{listing_id}"):
        assert not schema["paths"][PUBLIC + suffix]["get"].get("security")
    private = schema["paths"]["/api/v1/products/{product_id}/listing/activate"]["post"]
    assert private["security"] == [{"HTTPBearer": []}]
    assert {"401", "403", "404", "409", "422"} <= set(private["responses"])


@pytest.mark.parametrize("value", [False, "true", 1, None])
def test_activation_requires_strict_explicit_approval(
    market_client,
    market_headers,
    market_record,
    listing,
    value,
):
    path = market_record["path"] + "/listing"
    body = approval(market_client, market_headers, path)
    response = market_client.post(
        path + "/activate",
        headers=market_headers,
        json={**body, "approved": value},
    )
    assert response.status_code == 422
    assert market_client.get(PUBLIC).json()["items"] == []


@pytest.mark.parametrize(
    "price,minor", [("0.01", 1), ("19.25", 1925), ("1000000000", 100000000000)]
)
def test_public_price_minor_units_are_exact(
    market_client,
    market_headers,
    market_source,
    price,
    minor,
):
    record = market_source(price=price)
    path = record["path"] + "/listing"
    response = market_client.post(
        path,
        headers=market_headers,
        json={
            "passport_publication_id": record["publication"]["id"],
            "seller_display_name": "Example",
        },
    )
    assert response.status_code == 201
    assert activate(market_client, market_headers, path).status_code == 200
    with Session(market_client.app.state.engine) as db:
        assert db.get(MarketplaceListing, response.json()["id"]).price_minor == minor


def test_concurrent_duplicate_creates_return_conflict(
    market_client,
    market_url,
    market_headers,
    market_record,
    listing_content,
):
    path = market_record["path"] + "/listing"
    barrier = Barrier(2)
    applications = [create_app(market_url) for _ in range(2)]

    def create(index):
        with TestClient(applications[index]) as client:
            barrier.wait(timeout=10)
            return client.post(path, headers=market_headers, json=listing_content)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(create, range(2)))
    assert sorted(response.status_code for response in responses) == [201, 409]
