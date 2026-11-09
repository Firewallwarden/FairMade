"""Payment-gated pickup reports, ownership, privacy and append-only concurrency."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.main import create_app
from fairmade.models import (
    AccountRole,
    Order,
    PayPalCheckout,
    PickupFulfillmentEvent,
    RefundRequest,
)

BACKEND = Path(__file__).parents[2]
PRIVATE_TEXT = "PRIVATE_PICKUP_INSTRUCTIONS at synthetic location"


@pytest.fixture
def paid(paypal_client, buyer_headers, unpaid_order, checkout_path, checkout, fake_gateway):
    fake_gateway.approve(checkout["provider_order_id"])
    response = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert response.status_code == 200 and response.json()["state"] == "completed"
    return unpaid_order


def paths(order):
    buyer = "/api/v1/orders/" + order["id"] + "/fulfillment"
    return buyer, buyer.replace("/api/v1/orders/", "/api/v1/seller/orders/")


def body(revision=0, state="preparing", instructions=PRIVATE_TEXT):
    return {"expected_revision": revision, "state": state, "pickup_instructions": instructions}


def test_pickup_progress_is_separate_private_and_does_not_change_finances(
    paypal_client,
    paid,
    market_headers,
    buyer_headers,
    order_source,
):
    buyer, seller = paths(paid)
    initial = paypal_client.get(buyer, headers=buyer_headers).json()
    assert initial["state"] == "not_started" and initial["revision"] == 0
    assert initial["pickup_instructions"] is None and initial["updates_allowed"]
    inventory_path = order_source["path"] + "/inventory"
    inventory_before = paypal_client.get(inventory_path, headers=market_headers).json()
    for revision, state in enumerate(("preparing", "ready_for_pickup", "collected")):
        response = paypal_client.put(seller, headers=market_headers, json=body(revision, state))
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["revision"] == revision + 1 and data["state"] == state
        assert data["latest_event"]["created_at"].endswith("Z")
        assert data["basis"] == "seller_reported_unverified"
        assert paypal_client.get(buyer, headers=buyer_headers).json() == data
        assert response.headers["Cache-Control"] == "no-store"
        assert (
            "recorded_by_account_id" not in response.text
            and "seller_account_id" not in response.text
        )
    assert not data["updates_allowed"]
    assert paypal_client.get(inventory_path, headers=market_headers).json() == inventory_before
    order = paypal_client.get("/api/v1/orders/" + paid["id"], headers=buyer_headers)
    assert order.json()["status"] == "paid" and PRIVATE_TEXT not in order.text
    history = paypal_client.get(buyer + "/history?limit=2&offset=1", headers=buyer_headers).json()
    assert [item["revision"] for item in history["items"]] == [2, 1]
    assert PRIVATE_TEXT not in paypal_client.get("/api/v1/marketplace/listings").text
    assert PRIVATE_TEXT not in paypal_client.get("/api/v1/storefronts").text


def test_exact_retries_and_instruction_edits_preserve_event_history(
    paypal_client,
    paid,
    market_headers,
):
    _, seller = paths(paid)
    first = paypal_client.put(seller, headers=market_headers, json=body()).json()
    assert paypal_client.put(seller, headers=market_headers, json=body()).json() == first
    assert paypal_client.put(seller, headers=market_headers, json=body(1)).json() == first
    second = paypal_client.put(
        seller, headers=market_headers, json=body(1, instructions="New place")
    )
    assert second.status_code == 200 and second.json()["revision"] == 2
    assert paypal_client.put(seller, headers=market_headers, json=body()).status_code == 409
    events = paypal_client.get(seller + "/history", headers=market_headers).json()["items"]
    assert [row["pickup_instructions"] for row in events] == ["New place", PRIVATE_TEXT]


@pytest.mark.parametrize("state", ["ready_for_pickup", "collected"])
def test_cannot_skip_states(paypal_client, paid, market_headers, state):
    response = paypal_client.put(paths(paid)[1], headers=market_headers, json=body(0, state))
    assert (
        response.status_code == 409
        and response.json()["detail"]["code"] == "INVALID_PICKUP_TRANSITION"
    )


def test_collected_is_terminal_but_exact_retry_is_idempotent(paypal_client, paid, market_headers):
    _, seller = paths(paid)
    for revision, state in enumerate(("preparing", "ready_for_pickup", "collected")):
        result = paypal_client.put(seller, headers=market_headers, json=body(revision, state))
        assert result.status_code == 200
    assert (
        paypal_client.put(seller, headers=market_headers, json=body(2, "collected")).json()
        == result.json()
    )
    assert (
        paypal_client.put(seller, headers=market_headers, json=body(3, "preparing")).status_code
        == 409
    )
    assert (
        paypal_client.put(
            seller, headers=market_headers, json=body(3, "collected", "Changed address")
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "payment_state", ["absent", "ready", "capture_pending", "needs_review", "cancelled"]
)
def test_unverified_payments_cannot_start_pickup(
    paypal_client,
    unpaid_order,
    checkout,
    market_headers,
    payment_state,
):
    with Session(paypal_client.app.state.engine) as db, db.begin():
        payment = db.get(PayPalCheckout, unpaid_order["id"])
        if payment_state == "absent":
            db.delete(payment)
        elif payment_state == "cancelled":
            db.get(Order, unpaid_order["id"]).status = "cancelled"
        else:
            payment.state = payment_state
    response = paypal_client.put(paths(unpaid_order)[1], headers=market_headers, json=body())
    assert response.status_code == 409 and response.json()["detail"]["code"] == "ORDER_NOT_PAID"


def test_only_order_participants_can_read_and_only_current_seller_can_write(
    paypal_client,
    paid,
    market_headers,
    buyer_headers,
    market_account,
):
    buyer, seller = paths(paid)
    paypal_client.put(seller, headers=market_headers, json=body())
    other = market_account("unrelated-pickup@example.com")
    for url, headers, status in (
        (buyer, {}, 401),
        (buyer, other, 404),
        (seller, other, 404),
        (seller, buyer_headers, 403),
    ):
        for suffix in ("", "/history"):
            response = paypal_client.get(url + suffix, headers=headers)
            assert response.status_code == status and PRIVATE_TEXT not in response.text
    assert paypal_client.put(seller, headers=other, json=body()).status_code == 404
    assert paypal_client.put(buyer, headers=buyer_headers, json=body()).status_code == 405
    assert (
        paypal_client.get(
            buyer.replace(paid["id"], str(uuid4())), headers=buyer_headers
        ).status_code
        == 404
    )
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
    assert paypal_client.put(seller, headers=market_headers, json=body(1)).status_code == 403
    assert paypal_client.get(buyer, headers=buyer_headers).status_code == 200


@pytest.mark.parametrize(
    "refund_state", ["requested", "refund_pending", "needs_review", "refunded", "failed", "denied"]
)
def test_refund_gates_preserve_previous_pickup_history(
    paypal_client,
    paid,
    market_headers,
    buyer_headers,
    refund_state,
):
    buyer, seller = paths(paid)
    paypal_client.put(seller, headers=market_headers, json=body())
    created = paypal_client.post(
        "/api/v1/orders/" + paid["id"] + "/refund-request",
        headers=buyer_headers,
        json={"reason": "Synthetic refund"},
    )
    assert created.status_code == 201
    with Session(paypal_client.app.state.engine) as db, db.begin():
        seller_id = db.get(Order, paid["id"]).seller_account_id
        refund = db.scalar(select(RefundRequest).where(RefundRequest.order_id == paid["id"]))
        refund.state = refund_state
        if refund_state != "requested":
            refund.decision = "denied" if refund_state == "denied" else "approved"
            refund.decision_reason = "Synthetic seller decision"
            refund.decided_at = utcnow()
            refund.decided_by_account_id = seller_id
            refund.decision_revision = 1
        if refund_state == "refunded":
            refund.provider_refund_id = "SYNTHETICREFUND"
            refund.verified_at = utcnow()
    response = paypal_client.put(seller, headers=market_headers, json=body(1, "ready_for_pickup"))
    assert response.status_code == (200 if refund_state == "denied" else 409)
    if refund_state != "denied":
        assert response.json()["detail"]["code"] == "REFUND_BLOCKS_FULFILLMENT"
        snapshot = paypal_client.get(buyer, headers=buyer_headers).json()
        assert snapshot["state"] == "preparing" and not snapshot["updates_allowed"]
        assert snapshot["pickup_instructions"] == PRIVATE_TEXT


@pytest.mark.parametrize(
    "change",
    [
        {"expected_revision": -1},
        {"expected_revision": True},
        {"state": "delivered"},
        {"pickup_instructions": " "},
        {"pickup_instructions": "x" * 2001},
        {"state": "ready_for_pickup", "pickup_instructions": None},
        {"address": "PRIVATE_ADDRESS"},
    ],
)
def test_validation_redacts_private_instructions(paypal_client, paid, market_headers, change):
    response = paypal_client.put(paths(paid)[1], headers=market_headers, json={**body(), **change})
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert PRIVATE_TEXT not in response.text and "PRIVATE_ADDRESS" not in response.text
    assert all("input" not in item for item in response.json()["detail"])


def test_competing_updates_append_one_revision(paypal_client, paid, market_headers):
    _, seller = paths(paid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda text: paypal_client.put(
                    seller, headers=market_headers, json=body(instructions=text)
                ),
                ["Place A", "Place B"],
            )
        )
    assert sorted(result.status_code for result in results) == [200, 409]
    assert len(paypal_client.get(seller + "/history", headers=market_headers).json()["items"]) == 1


def test_failed_commit_does_not_append_progress(paypal_client, paid, market_headers, market_url):
    def fail(db):
        if any(isinstance(item, PickupFulfillmentEvent) for item in db.new):
            raise RuntimeError("Synthetic pickup persistence failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert (
                client.put(paths(paid)[1], headers=market_headers, json=body()).status_code == 500
            )
    finally:
        event.remove(Session, "before_commit", fail)
    assert paypal_client.get(paths(paid)[1], headers=market_headers).json()["revision"] == 0


def test_identical_concurrent_retries_create_one_event(paypal_client, paid, market_headers):
    _, seller = paths(paid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: paypal_client.put(seller, headers=market_headers, json=body()), range(2)
            )
        )
    assert all(result.status_code == 200 for result in results)
    assert results[0].json() == results[1].json()
    assert len(paypal_client.get(seller + "/history", headers=market_headers).json()["items"]) == 1


def test_refund_request_race_serializes_with_pickup_update(
    paypal_client,
    paid,
    market_headers,
    buyer_headers,
):
    buyer, seller = paths(paid)
    refund_path = "/api/v1/orders/" + paid["id"] + "/refund-request"
    with ThreadPoolExecutor(max_workers=2) as pool:
        pickup_future = pool.submit(paypal_client.put, seller, headers=market_headers, json=body())
        refund_future = pool.submit(
            paypal_client.post,
            refund_path,
            headers=buyer_headers,
            json={"reason": "Synthetic racing refund"},
        )
        pickup, refund = pickup_future.result(), refund_future.result()
    assert refund.status_code == 201 and pickup.status_code in (200, 409)
    latest = paypal_client.get(buyer, headers=buyer_headers).json()
    assert not latest["updates_allowed"]
    if pickup.status_code == 200:
        assert pickup.json()["latest_event"]["created_at"] <= refund.json()["created_at"]
    else:
        assert latest["revision"] == 0


def test_restart_metadata_and_downgrade_guard_preserve_private_history(
    paypal_client,
    paid,
    market_headers,
    buyer_headers,
    market_url,
):
    buyer, seller = paths(paid)
    expected = paypal_client.put(seller, headers=market_headers, json=body()).json()
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="pickup history records"):
        command.downgrade(config, "0016")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(buyer, headers=buyer_headers).json() == expected
    with paypal_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_openapi_preserves_auth_and_documents_private_routes(paypal_client):
    schema = paypal_client.get("/openapi.json").json()
    for path, operations in schema["paths"].items():
        if "/fulfillment" in path:
            for operation in operations.values():
                assert operation["security"] == [{"HTTPBearer": []}]
    assert not any("fulfillment" in path for path in schema["paths"] if "/marketplace/" in path)
