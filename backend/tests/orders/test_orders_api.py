"""Authorization, exact snapshots, stock isolation, retries, expiry and concurrency."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from fairmade.inventory import service as inventory_service
from fairmade.main import create_app
from fairmade.models import Order, OrderLine
from fairmade.orders import service

ORDERS = "/api/v1/orders"


def headers_with_key(headers, key=None):
    return {**headers, "Idempotency-Key": key or str(uuid4())}


def create(client, headers, cart, key=None):
    return client.post(ORDERS, headers=headers_with_key(headers, key), json=cart)


def inventory(client, headers, source):
    return client.get(source["path"] + "/inventory", headers=headers).json()


def test_preview_does_not_reserve_and_order_snapshot_is_exact(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    cart,
):
    preview = market_client.post(ORDERS + "/preview", headers=buyer_headers, json=cart)
    assert preview.status_code == 200, preview.text
    assert preview.json()["subtotal"] == {"currency": "USD", "amount": "34.00"}
    assert inventory(market_client, market_headers, order_source)["reserved"] == 0
    created = create(market_client, buyer_headers, cart)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "pending_payment" and body["snapshot"] == preview.json()
    assert datetime.fromisoformat(body["expires_at"]) - datetime.fromisoformat(
        body["created_at"]
    ) == timedelta(minutes=15)
    current = inventory(market_client, market_headers, order_source)
    assert (current["on_hand"], current["reserved"], current["available"]) == (10, 2, 8)
    assert "PRIVATE_MARKET" not in json.dumps(body)
    assert "@example.com" not in json.dumps(body)
    assert order_source["product"]["id"] not in json.dumps(body)
    assert body["snapshot"]["notices"] and created.headers["Cache-Control"] == "no-store"
    assert market_client.get(ORDERS, headers=buyer_headers).json()["items"] == [body]
    assert market_client.get("/api/v1/seller/orders", headers=market_headers).json()["items"] == [
        body
    ]
    with Session(market_client.app.state.engine) as db:
        order = db.get(Order, body["id"])
        assert order.subtotal_minor == 3400
        assert db.scalar(select(func.count()).select_from(OrderLine)) == 1


def test_retry_uses_original_order_even_after_listing_withdrawal_and_cancel(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    cart,
):
    key = str(uuid4())
    first = create(market_client, buyer_headers, cart, key).json()
    assert (
        market_client.post(
            ORDERS + "/" + first["id"] + "/cancel", headers=buyer_headers
        ).status_code
        == 200
    )
    assert (
        market_client.post(
            order_source["path"] + "/listing/deactivate", headers=market_headers
        ).status_code
        == 204
    )
    repeated = create(market_client, buyer_headers, cart, key)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == first["id"] and repeated.json()["status"] == "cancelled"
    assert inventory(market_client, market_headers, order_source)["reserved"] == 0
    changed = {"items": [{**cart["items"][0], "quantity": 3}]}
    assert (
        create(market_client, buyer_headers, changed, key).json()["detail"]["code"]
        == "IDEMPOTENCY_CONFLICT"
    )


@pytest.mark.parametrize("seller_cancels", [True, False])
def test_cancellation_releases_once_and_history_survives_deactivation(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    cart,
    seller_cancels,
):
    order = create(market_client, buyer_headers, cart).json()
    base = "/api/v1/seller/orders" if seller_cancels else ORDERS
    headers = market_headers if seller_cancels else buyer_headers
    response = market_client.post(base + "/" + order["id"] + "/cancel", headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert (
        market_client.post(base + "/" + order["id"] + "/cancel", headers=headers).json()
        == response.json()
    )
    assert inventory(market_client, market_headers, order_source)["available"] == 10
    assert (
        market_client.post(
            order_source["path"] + "/listing/deactivate", headers=market_headers
        ).status_code
        == 204
    )
    historical = market_client.get(ORDERS + "/" + order["id"], headers=buyer_headers)
    assert historical.status_code == 200 and historical.json()["snapshot"] == order["snapshot"]
    assert create(market_client, buyer_headers, cart).status_code == 404


def test_expiry_releases_at_exact_deadline_without_background_jobs(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    cart,
    monkeypatch,
):
    order = create(market_client, buyer_headers, cart).json()
    deadline = datetime.fromisoformat(order["expires_at"])
    monkeypatch.setattr(service, "utcnow", lambda: deadline - timedelta(microseconds=1))
    monkeypatch.setattr(inventory_service, "utcnow", lambda: deadline - timedelta(microseconds=1))
    assert inventory(market_client, market_headers, order_source)["reserved"] == 2
    monkeypatch.setattr(service, "utcnow", lambda: deadline)
    monkeypatch.setattr(inventory_service, "utcnow", lambda: deadline)
    assert inventory(market_client, market_headers, order_source)["reserved"] == 0
    response = market_client.get(ORDERS + "/" + order["id"], headers=buyer_headers)
    assert response.json()["status"] == "expired"
    assert (
        market_client.post(ORDERS + "/" + order["id"] + "/cancel", headers=buyer_headers).json()[
            "status"
        ]
        == "expired"
    )
    assert create(market_client, buyer_headers, cart).status_code == 201


def test_inventory_revision_reservations_and_basis_guards(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    cart,
):
    path = order_source["path"] + "/inventory"
    order = create(market_client, buyer_headers, cart).json()
    for body, code in [
        ({"expected_revision": 0, "selling_unit": "loaf", "on_hand": 10}, "REVISION_CONFLICT"),
        ({"expected_revision": 1, "selling_unit": "loaf", "on_hand": 1}, "STOCK_RESERVED"),
        ({"expected_revision": 1, "selling_unit": "kg", "on_hand": 10}, "INVENTORY_UNIT_LOCKED"),
    ]:
        response = market_client.put(path, headers=market_headers, json=body)
        assert response.status_code == 409 and response.json()["detail"]["code"] == code
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={"expected_revision": 1, "selling_unit": "loaf", "on_hand": 3},
        ).status_code
        == 200
    )
    assert inventory(market_client, market_headers, order_source)["available"] == 1
    assert (
        create(market_client, buyer_headers, cart).json()["detail"]["code"] == "INSUFFICIENT_STOCK"
    )
    market_client.post(ORDERS + "/" + order["id"] + "/cancel", headers=buyer_headers)
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={"expected_revision": 2, "selling_unit": "loaf", "on_hand": 0},
        ).status_code
        == 200
    )
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={"expected_revision": 3, "selling_unit": "kg", "on_hand": 10},
        ).status_code
        == 200
    )
    assert (
        create(market_client, buyer_headers, cart).json()["detail"]["code"]
        == "INVENTORY_UNIT_MISMATCH"
    )


def test_stale_listing_and_private_draft_edit_behavior(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    listing_content,
    cart,
):
    path = order_source["path"] + "/listing"
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={**listing_content, "expected_revision": 1, "summary": "Private draft change"},
        ).status_code
        == 200
    )
    # Public revision 1 is still authoritative while draft revision is 2.
    first = create(market_client, buyer_headers, cart)
    assert first.status_code == 201
    preview = market_client.get(path + "/preview", headers=market_headers).json()
    assert (
        market_client.post(
            path + "/activate",
            headers=market_headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        ).status_code
        == 200
    )
    response = create(market_client, buyer_headers, cart)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "LISTING_CHANGED"


@pytest.mark.parametrize("quantity", [0, -1, True, "2", 10001])
def test_invalid_quantity_is_rejected(market_client, buyer_headers, cart, quantity):
    response = create(
        market_client, buyer_headers, {"items": [{**cart["items"][0], "quantity": quantity}]}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "extra",
    [
        {"unit_price": "0.01"},
        {"total": "0.01"},
        {"status": "paid"},
        {"seller_account_id": str(uuid4())},
    ],
)
def test_client_cannot_set_price_or_order_state(market_client, buyer_headers, cart, extra):
    assert create(market_client, buyer_headers, {**cart, **extra}).status_code == 422


def test_request_and_key_validation(market_client, buyer_headers, cart):
    assert market_client.post(ORDERS, headers=buyer_headers, json=cart).status_code == 422
    assert create(market_client, buyer_headers, cart, "invalid-key").status_code == 422
    assert create(market_client, buyer_headers, {"items": []}).status_code == 422
    assert create(market_client, buyer_headers, {"items": cart["items"] * 2}).status_code == 422


def test_self_purchase_and_cross_account_order_privacy(
    market_client,
    market_account,
    market_headers,
    buyer_headers,
    order_source,
    cart,
):
    assert create(market_client, market_headers, cart).json()["detail"]["code"] == "SELF_PURCHASE"
    order = create(market_client, buyer_headers, cart).json()
    other_buyer = market_account("other-buyer@example.com", roles=())
    other_seller = market_account("other-seller@example.com")
    for base, headers in [(ORDERS, other_buyer), ("/api/v1/seller/orders", other_seller)]:
        assert market_client.get(base, headers=headers).json()["items"] == []
        assert market_client.get(base + "/" + order["id"], headers=headers).status_code == 404
        assert (
            market_client.post(base + "/" + order["id"] + "/cancel", headers=headers).status_code
            == 404
        )
    assert market_client.get("/api/v1/seller/orders", headers=buyer_headers).status_code == 403
    path = order_source["path"] + "/inventory"
    assert market_client.get(path, headers=buyer_headers).status_code == 403
    assert market_client.get(path, headers=other_seller).status_code == 404
    assert (
        market_client.put(
            path,
            headers=other_seller,
            json={"expected_revision": 1, "selling_unit": "loaf", "on_hand": 10},
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", ORDERS),
        ("post", ORDERS + "/preview"),
        ("get", ORDERS),
        ("get", ORDERS + "/" + str(uuid4())),
        ("post", ORDERS + "/" + str(uuid4()) + "/cancel"),
        ("get", "/api/v1/seller/orders"),
    ],
)
def test_authentication_is_required(market_client, method, path):
    assert market_client.request(method, path, json={}).status_code == 401


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_orders_never_oversell(
    market_client,
    market_url,
    market_headers,
    buyer_headers,
    order_source,
    cart,
    same_key,
):
    path = order_source["path"] + "/inventory"
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={"expected_revision": 1, "selling_unit": "loaf", "on_hand": 2},
        ).status_code
        == 200
    )
    apps = [create_app(market_url) for _ in range(2)]
    barrier = Barrier(2)
    keys = [str(uuid4()), str(uuid4())]
    if same_key:
        keys[1] = keys[0]

    def submit(index):
        with TestClient(apps[index]) as client:
            barrier.wait(timeout=10)
            return create(client, buyer_headers, cart, keys[index])

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, range(2)))
    assert sorted(r.status_code for r in responses) == ([200, 201] if same_key else [201, 409])
    assert inventory(market_client, market_headers, order_source)["reserved"] == 2
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1


def test_multiline_total_and_all_or_nothing_reservation(
    market_client,
    market_source,
    market_headers,
    buyer_headers,
    order_source,
    cart,
):
    other = market_source(price="0.01")
    path = other["path"]
    draft = market_client.post(
        path + "/listing",
        headers=market_headers,
        json={
            "passport_publication_id": other["publication"]["id"],
            "seller_display_name": "Example",
        },
    ).json()
    p = market_client.get(path + "/listing/preview", headers=market_headers).json()
    assert (
        market_client.post(
            path + "/listing/activate",
            headers=market_headers,
            json={
                "expected_revision": p["revision"],
                "preview_hash": p["preview_hash"],
                "approved": True,
            },
        ).status_code
        == 200
    )
    other_line = {"listing_id": draft["id"], "expected_listing_revision": 1, "quantity": 3}
    mixed = {"items": [*cart["items"], other_line]}
    assert (
        create(market_client, buyer_headers, mixed).json()["detail"]["code"]
        == "INVENTORY_NOT_CONFIGURED"
    )
    assert inventory(market_client, market_headers, order_source)["reserved"] == 0
    assert (
        market_client.put(
            path + "/inventory",
            headers=market_headers,
            json={"expected_revision": 0, "selling_unit": "loaf", "on_hand": 4},
        ).status_code
        == 200
    )
    key = str(uuid4())
    response = create(market_client, buyer_headers, mixed, key)
    assert (
        response.status_code == 201 and response.json()["snapshot"]["subtotal"]["amount"] == "34.03"
    )
    reordered = create(market_client, buyer_headers, {"items": list(reversed(mixed["items"]))}, key)
    assert reordered.status_code == 200 and reordered.json()["id"] == response.json()["id"]


@pytest.mark.parametrize("operation", ["create", "cancel", "inventory"])
def test_failed_transactions_leave_stock_and_orders_unchanged(
    market_client,
    market_url,
    market_headers,
    buyer_headers,
    order_source,
    cart,
    operation,
):
    order = create(market_client, buyer_headers, cart).json() if operation == "cancel" else None
    before = inventory(market_client, market_headers, order_source)

    def fail(_db):
        raise RuntimeError("Synthetic reservation failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            if operation == "create":
                response = create(client, buyer_headers, cart)
            elif operation == "cancel":
                response = client.post(
                    ORDERS + "/" + order["id"] + "/cancel", headers=buyer_headers
                )
            else:
                response = client.put(
                    order_source["path"] + "/inventory",
                    headers=market_headers,
                    json={"expected_revision": 1, "selling_unit": "loaf", "on_hand": 20},
                )
            assert response.status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert inventory(market_client, market_headers, order_source) == before
    assert len(market_client.get(ORDERS, headers=buyer_headers).json()["items"]) == (
        1 if order else 0
    )


def test_migration_restart_and_openapi(
    market_client,
    market_url,
    market_headers,
    buyer_headers,
    order_source,
    cart,
):
    order = create(market_client, buyer_headers, cart).json()
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(ORDERS + "/" + order["id"], headers=buyer_headers).json() == order
        assert inventory(restarted, market_headers, order_source)["reserved"] == 2
    with market_client.app.state.engine.connect() as conn:
        before = conn.execute(text("SELECT * FROM marketplace_listings ORDER BY id")).all()
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.check(config)
    command.downgrade(config, "0007")
    command.upgrade(config, "head")
    with market_client.app.state.engine.connect() as conn:
        assert conn.execute(text("SELECT * FROM marketplace_listings ORDER BY id")).all() == before
        assert conn.execute(text("PRAGMA foreign_key_check")).all() == []
    assert market_client.get(ORDERS, headers=buyer_headers).json()["items"] == []
    schema = market_client.get("/openapi.json").json()
    for path in (ORDERS, ORDERS + "/preview", "/api/v1/seller/orders"):
        for endpoint in schema["paths"][path].values():
            assert endpoint["security"] == [{"HTTPBearer": []}]
    assert not any("/capture" in path or "/paid" in path for path in schema["paths"])


def test_concurrent_first_inventory_configuration_is_revision_safe(
    market_client,
    market_url,
    market_headers,
    market_record,
):
    path = market_record["path"] + "/inventory"
    empty = market_client.get(path, headers=market_headers).json()
    assert empty["configured"] is False and empty["revision"] == 0
    apps = [create_app(market_url) for _ in range(2)]
    barrier = Barrier(2)

    def configure(index):
        with TestClient(apps[index]) as client:
            barrier.wait(timeout=10)
            return client.put(
                path,
                headers=market_headers,
                json={"expected_revision": 0, "selling_unit": "loaf", "on_hand": 10 + index},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(configure, range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert market_client.get(path, headers=market_headers).json()["revision"] == 1


@pytest.mark.parametrize("amount", [-1, True, "10", 1.5, 1000001])
def test_inventory_input_bounds(market_client, market_headers, market_record, amount):
    response = market_client.put(
        market_record["path"] + "/inventory",
        headers=market_headers,
        json={"expected_revision": 0, "selling_unit": "loaf", "on_hand": amount},
    )
    assert response.status_code == 422


def test_order_amount_limit_rolls_back_all_reservations(
    market_client,
    market_source,
    market_headers,
    buyer_headers,
):
    record = market_source(price="1000000000")
    path = record["path"]
    listing = market_client.post(
        path + "/listing",
        headers=market_headers,
        json={
            "passport_publication_id": record["publication"]["id"],
            "seller_display_name": "Example",
        },
    ).json()
    p = market_client.get(path + "/listing/preview", headers=market_headers).json()
    market_client.post(
        path + "/listing/activate",
        headers=market_headers,
        json={
            "expected_revision": p["revision"],
            "preview_hash": p["preview_hash"],
            "approved": True,
        },
    )
    assert (
        market_client.put(
            path + "/inventory",
            headers=market_headers,
            json={
                "expected_revision": 0,
                "selling_unit": "loaf",
                "on_hand": 10,
            },
        ).status_code
        == 200
    )
    body = {"items": [{"listing_id": listing["id"], "expected_listing_revision": 1, "quantity": 2}]}
    response = create(market_client, buyer_headers, body)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "ORDER_AMOUNT_LIMIT"
    assert inventory(market_client, market_headers, record)["reserved"] == 0


def test_one_seller_per_order_and_buyer_scoped_idempotency(
    market_client,
    market_source,
    market_account,
    market_headers,
    buyer_headers,
    order_source,
    cart,
):
    second_seller = market_account("separate-seller@example.com")
    record = market_source(headers=second_seller)
    path = record["path"]
    listing = market_client.post(
        path + "/listing",
        headers=second_seller,
        json={
            "passport_publication_id": record["publication"]["id"],
            "seller_display_name": "Other",
        },
    ).json()
    p = market_client.get(path + "/listing/preview", headers=second_seller).json()
    assert (
        market_client.post(
            path + "/listing/activate",
            headers=second_seller,
            json={
                "expected_revision": p["revision"],
                "preview_hash": p["preview_hash"],
                "approved": True,
            },
        ).status_code
        == 200
    )
    assert (
        market_client.put(
            path + "/inventory",
            headers=second_seller,
            json={
                "expected_revision": 0,
                "selling_unit": "loaf",
                "on_hand": 10,
            },
        ).status_code
        == 200
    )
    mixed = {
        "items": [
            *cart["items"],
            {
                "listing_id": listing["id"],
                "expected_listing_revision": 1,
                "quantity": 1,
            },
        ]
    }
    response = create(market_client, buyer_headers, mixed)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "MULTIPLE_SELLERS"
    assert inventory(market_client, market_headers, order_source)["reserved"] == 0
    assert inventory(market_client, second_seller, record)["reserved"] == 0
    key = str(uuid4())
    first = create(market_client, buyer_headers, cart, key).json()
    other_buyer = market_account("another-order-buyer@example.com", roles=())
    second = create(market_client, other_buyer, cart, key)
    assert second.status_code == 201 and second.json()["id"] != first["id"]
