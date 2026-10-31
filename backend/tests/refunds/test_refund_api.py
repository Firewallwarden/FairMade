"""Buyer requests, seller authority, verified refunds and retry/crash behavior."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event, Thread
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import RefundRequest
from fairmade.refunds import service


def stock(client, headers, source):
    return client.get(source["path"] + "/inventory", headers=headers).json()


def approve(client, headers, path):
    return client.post(path + "/approve", headers=headers, json={"expected_revision": 1})


def test_request_is_private_idempotent_and_does_not_move_money(
    paypal_client,
    fake_gateway,
    buyer_headers,
    market_headers,
    order_source,
    paid_order,
    refund_path,
    seller_refund_path,
    refund_request,
):
    assert refund_request["state"] == "requested" and refund_request["decision"] is None
    assert refund_request["amount"] == {"currency": "USD", "amount": "34.00"}
    repeat = paypal_client.post(
        refund_path, headers=buyer_headers, json={"reason": refund_request["reason"]}
    )
    assert repeat.status_code == 200 and repeat.json() == refund_request
    assert (
        paypal_client.post(
            refund_path, headers=buyer_headers, json={"reason": "Different"}
        ).status_code
        == 409
    )
    assert paypal_client.get(refund_path, headers=buyer_headers).json() == refund_request
    assert paypal_client.get(seller_refund_path, headers=market_headers).json() == refund_request
    assert paypal_client.get("/api/v1/refund-requests", headers=buyer_headers).json()["items"] == [
        refund_request
    ]
    assert paypal_client.get("/api/v1/seller/refund-requests", headers=market_headers).json()[
        "items"
    ] == [refund_request]
    assert fake_gateway.refund_calls == []
    assert stock(paypal_client, market_headers, order_source)["on_hand"] == 8
    assert (
        paypal_client.get("/api/v1/orders/" + paid_order["id"], headers=buyer_headers).json()[
            "status"
        ]
        == "paid"
    )


def test_seller_denial_is_audited_final_and_idempotent(
    paypal_client,
    fake_gateway,
    market_headers,
    buyer_headers,
    refund_request,
    seller_refund_path,
):
    body = {"expected_revision": 1, "reason": "Synthetic seller denial reason"}
    denied = paypal_client.post(seller_refund_path + "/deny", headers=market_headers, json=body)
    assert denied.status_code == 200 and denied.json()["state"] == "denied"
    assert (
        denied.json()["decision"] == "denied" and denied.json()["decision_reason"] == body["reason"]
    )
    assert denied.json()["decided_at"].endswith("Z")
    assert (
        paypal_client.post(seller_refund_path + "/deny", headers=market_headers, json=body).json()
        == denied.json()
    )
    assert approve(paypal_client, market_headers, seller_refund_path).status_code == 409
    assert (
        paypal_client.post(
            seller_refund_path + "/deny", headers=market_headers, json={**body, "reason": "Changed"}
        ).status_code
        == 409
    )
    assert fake_gateway.refund_calls == []
    with Session(paypal_client.app.state.engine) as db:
        request = db.get(RefundRequest, refund_request["id"])
        assert request.decided_by_account_id is not None
        assert request.requested_by_account_id != request.decided_by_account_id


def test_verified_approval_refunds_once_and_never_auto_restocks(
    paypal_client,
    fake_gateway,
    market_headers,
    buyer_headers,
    order_source,
    paid_order,
    refund_request,
    refund_path,
    seller_refund_path,
):
    before = stock(paypal_client, market_headers, order_source)
    result = approve(paypal_client, market_headers, seller_refund_path)
    assert result.status_code == 200, result.text
    refunded = result.json()
    assert refunded["state"] == "refunded" and refunded["decision"] == "approved"
    assert refunded["verified_at"] and refunded["provider_refund_id"]
    assert "PRIVATE_" not in json.dumps(refunded)
    assert "merchant_id" not in refunded and "requested_by_account_id" not in refunded
    assert approve(paypal_client, market_headers, seller_refund_path).json() == refunded
    assert (
        paypal_client.post(refund_path + "/reconcile", headers=buyer_headers, json={}).json()
        == refunded
    )
    assert len(fake_gateway.refund_calls) == 1
    assert fake_gateway.refund_calls[0][2] == 3400
    assert stock(paypal_client, market_headers, order_source) == before
    order = paypal_client.get("/api/v1/orders/" + paid_order["id"], headers=buyer_headers).json()
    assert order["status"] == "refunded" and order["snapshot"] == paid_order["snapshot"]
    assert (
        paypal_client.post(
            "/api/v1/orders/" + paid_order["id"] + "/cancel", headers=buyer_headers
        ).status_code
        == 409
    )
    receipt = paypal_client.get(
        "/api/v1/orders/" + paid_order["id"] + "/paypal-checkout", headers=buyer_headers
    ).json()
    assert receipt["state"] == "completed"  # Original capture history remains intact.


@pytest.mark.parametrize("behavior,state", [("pending", "refund_pending"), ("failed", "failed")])
def test_noncompleted_provider_result_never_claims_refunded(
    paypal_client,
    fake_gateway,
    market_headers,
    buyer_headers,
    paid_order,
    order_source,
    refund_request,
    seller_refund_path,
    behavior,
    state,
):
    fake_gateway.refund_behavior = behavior
    result = approve(paypal_client, market_headers, seller_refund_path)
    assert result.status_code == 200 and result.json()["state"] == state
    order = paypal_client.get("/api/v1/orders/" + paid_order["id"], headers=buyer_headers).json()
    assert order["status"] == ("refund_pending" if behavior == "pending" else "paid")
    assert stock(paypal_client, market_headers, order_source)["on_hand"] == 8


def test_buyer_reconcile_only_reads_known_approved_refund(
    paypal_client,
    fake_gateway,
    market_headers,
    buyer_headers,
    refund_path,
    seller_refund_path,
    refund_request,
):
    # An unapproved request causes no provider action.
    assert (
        paypal_client.post(refund_path + "/reconcile", headers=buyer_headers, json={}).json()
        == refund_request
    )
    assert fake_gateway.refund_calls == []
    fake_gateway.refund_behavior = "pending"
    pending = approve(paypal_client, market_headers, seller_refund_path).json()
    fake_gateway.refunds[pending["provider_refund_id"]]["status"] = "COMPLETED"
    result = paypal_client.post(refund_path + "/reconcile", headers=buyer_headers, json={})
    assert result.status_code == 200 and result.json()["state"] == "refunded"
    assert len(fake_gateway.refund_calls) == 1


@pytest.mark.parametrize("behavior", ["timeout_before", "timeout_after"])
def test_uncertain_refund_retries_use_identical_key_and_amount(
    paypal_client,
    fake_gateway,
    market_headers,
    buyer_headers,
    refund_path,
    seller_refund_path,
    refund_request,
    behavior,
):
    fake_gateway.refund_behavior = behavior
    assert approve(paypal_client, market_headers, seller_refund_path).status_code == 502
    unknown = paypal_client.post(refund_path + "/reconcile", headers=buyer_headers, json={})
    assert (
        unknown.status_code == 409 and unknown.json()["detail"]["code"] == "REFUND_RESULT_UNKNOWN"
    )
    fake_gateway.refund_behavior = "success"
    result = approve(paypal_client, market_headers, seller_refund_path)
    assert result.status_code == 200 and result.json()["state"] == "refunded"
    assert len(fake_gateway.refunds) == 1
    assert fake_gateway.refund_calls[0] == fake_gateway.refund_calls[1]


def test_known_id_recovers_provider_read_failure_without_second_refund_post(
    paypal_client,
    fake_gateway,
    market_headers,
    buyer_headers,
    refund_path,
    seller_refund_path,
    refund_request,
):
    fake_gateway.refund_fetch_error = True
    assert approve(paypal_client, market_headers, seller_refund_path).status_code == 502
    fake_gateway.refund_fetch_error = False
    assert (
        paypal_client.post(refund_path + "/reconcile", headers=buyer_headers, json={}).json()[
            "state"
        ]
        == "refunded"
    )
    assert len(fake_gateway.refund_calls) == 1


def test_stale_revision_cannot_decide(
    paypal_client,
    fake_gateway,
    market_headers,
    seller_refund_path,
    refund_request,
):
    for suffix, body in [
        ("/approve", {"expected_revision": 2}),
        ("/deny", {"expected_revision": 2, "reason": "Denied"}),
    ]:
        result = paypal_client.post(seller_refund_path + suffix, headers=market_headers, json=body)
        assert result.status_code == 409 and result.json()["detail"]["code"] == "REVISION_CONFLICT"
    assert fake_gateway.refund_calls == []


@pytest.mark.parametrize(
    "extra",
    [
        {"amount": "0.01"},
        {"currency": "EUR"},
        {"status": "refunded"},
        {"restock": True},
        {"seller_id": str(uuid4())},
    ],
)
def test_clients_cannot_supply_financial_or_workflow_fields(
    paypal_client,
    market_headers,
    buyer_headers,
    refund_path,
    seller_refund_path,
    refund_request,
    extra,
):
    assert (
        paypal_client.post(
            refund_path, headers=buyer_headers, json={"reason": "Example", **extra}
        ).status_code
        == 422
    )
    assert (
        paypal_client.post(
            seller_refund_path + "/approve",
            headers=market_headers,
            json={"expected_revision": 1, **extra},
        ).status_code
        == 422
    )


@pytest.mark.parametrize("reason", ["", " ", "x" * 1001, True])
def test_reasons_are_bounded_and_not_echoed(paypal_client, buyer_headers, refund_path, reason):
    response = paypal_client.post(refund_path, headers=buyer_headers, json={"reason": reason})
    assert response.status_code == 422
    assert "input" not in response.json()["detail"][0]


def test_only_paid_order_buyer_may_request(paypal_client, buyer_headers, unpaid_order):
    path = "/api/v1/orders/" + unpaid_order["id"] + "/refund-request"
    response = paypal_client.post(path, headers=buyer_headers, json={"reason": "Synthetic"})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "ORDER_NOT_PAID"


def test_authorization_and_participant_privacy(
    paypal_client,
    fake_gateway,
    market_account,
    market_headers,
    buyer_headers,
    refund_request,
    refund_path,
    seller_refund_path,
):
    stranger = market_account("stranger-refund-buyer@example.com", roles=())
    other_seller = market_account("stranger-refund-seller@example.com")
    for method, url, body in [
        ("get", refund_path, None),
        ("post", refund_path, {"reason": "Synthetic"}),
        ("post", refund_path + "/reconcile", {}),
    ]:
        assert paypal_client.request(method, url, headers=stranger, json=body).status_code == 404
        assert paypal_client.request(method, url, json=body).status_code == 401
    for suffix, body in [
        ("/approve", {"expected_revision": 1}),
        ("/deny", {"expected_revision": 1, "reason": "Synthetic"}),
        ("/reconcile", {}),
    ]:
        assert (
            paypal_client.post(
                seller_refund_path + suffix, headers=buyer_headers, json=body
            ).status_code
            == 403
        )
        assert (
            paypal_client.post(
                seller_refund_path + suffix, headers=other_seller, json=body
            ).status_code
            == 404
        )
        assert paypal_client.post(seller_refund_path + suffix, json=body).status_code == 401
    assert paypal_client.get(seller_refund_path, headers=buyer_headers).status_code == 403
    assert paypal_client.get("/api/v1/refund-requests", headers=stranger).json()["items"] == []
    assert (
        paypal_client.get("/api/v1/seller/refund-requests", headers=other_seller).json()["items"]
        == []
    )
    assert fake_gateway.refund_calls == []


@pytest.mark.parametrize(
    "change", ["amount", "currency", "id", "invoice", "parent_capture", "parent_host", "status"]
)
def test_invalid_refund_evidence_requires_review_not_refunded(
    paypal_client,
    fake_gateway,
    market_headers,
    buyer_headers,
    paid_order,
    refund_request,
    refund_path,
    seller_refund_path,
    change,
):
    fake_gateway.refund_behavior = "pending"
    pending = approve(paypal_client, market_headers, seller_refund_path).json()
    data = fake_gateway.refunds[pending["provider_refund_id"]]
    if change == "amount":
        data["amount"]["value"] = "0.01"
    elif change == "currency":
        data["amount"]["currency_code"] = "EUR"
    elif change == "id":
        data["id"] = "WRONGREFUND"
    elif change == "invoice":
        data["invoice_id"] = "wrong-request"
    elif change == "parent_capture":
        data["links"][0]["href"] = "https://api-m.sandbox.paypal.com/v2/payments/captures/OTHER"
    elif change == "parent_host":
        data["links"][0]["href"] = data["links"][0]["href"].replace(
            "api-m.sandbox.paypal.com", "untrusted.example"
        )
    else:
        data["status"] = "UNKNOWN"
    result = paypal_client.post(refund_path + "/reconcile", headers=buyer_headers, json={})
    assert (
        result.status_code == 502
        and result.json()["detail"]["code"] == "REFUND_VERIFICATION_FAILED"
    )
    assert (
        paypal_client.get("/api/v1/orders/" + paid_order["id"], headers=buyer_headers).json()[
            "status"
        ]
        == "refund_review"
    )


def test_original_capture_binding_is_verified_before_refunding(
    paypal_client,
    fake_gateway,
    market_headers,
    refund_request,
    seller_refund_path,
):
    fake_gateway.capture_override = lambda capture: capture["payee"].update(merchant_id="OTHER")
    result = approve(paypal_client, market_headers, seller_refund_path)
    assert result.status_code == 502 and fake_gateway.refund_calls == []


def test_concurrent_create_returns_one_request(
    paypal_client,
    market_url,
    fake_gateway,
    buyer_headers,
    refund_path,
):
    apps = [create_app(market_url, paypal_gateway=fake_gateway) for _ in range(2)]
    barrier = Barrier(2)

    def create(index):
        with TestClient(apps[index]) as client:
            barrier.wait(timeout=10)
            return client.post(refund_path, headers=buyer_headers, json={"reason": "Same reason"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, range(2)))
    assert sorted(r.status_code for r in results) == [200, 201]
    assert results[0].json()["id"] == results[1].json()["id"]
    assert fake_gateway.refund_calls == []


def test_seller_decision_race_and_retry_do_not_issue_duplicate_refunds(
    paypal_client,
    fake_gateway,
    market_url,
    market_headers,
    seller_refund_path,
    refund_request,
):
    entered, resume = Event(), Event()
    original = fake_gateway.refund
    app = create_app(market_url, paypal_gateway=fake_gateway)
    results = []

    def slow(*args):
        entered.set()
        assert resume.wait(timeout=10)
        return original(*args)

    fake_gateway.refund = slow

    def submit():
        with TestClient(app) as client:
            results.append(approve(client, market_headers, seller_refund_path))

    worker = Thread(target=submit)
    worker.start()
    try:
        assert entered.wait(timeout=10)
        denied = paypal_client.post(
            seller_refund_path + "/deny",
            headers=market_headers,
            json={"expected_revision": 1, "reason": "Racing denial"},
        )
        assert denied.status_code == 409
        assert approve(paypal_client, market_headers, seller_refund_path).status_code == 409
    finally:
        resume.set()
        worker.join(timeout=15)
    assert results and results[0].status_code == 200
    assert len(fake_gateway.refund_calls) == 1


@pytest.mark.parametrize("phase", ["approval", "settlement"])
def test_failed_commit_cannot_fabricate_decision_or_repeat_provider_refund(
    paypal_client,
    fake_gateway,
    market_url,
    market_headers,
    buyer_headers,
    refund_request,
    refund_path,
    seller_refund_path,
    phase,
):
    def fail_commit(db):
        state = "refund_pending" if phase == "approval" else "refunded"
        if any(isinstance(obj, RefundRequest) and obj.state == state for obj in db.dirty):
            raise RuntimeError("Synthetic refund persistence failure")

    event.listen(Session, "before_commit", fail_commit)
    try:
        with TestClient(
            create_app(market_url, paypal_gateway=fake_gateway), raise_server_exceptions=False
        ) as client:
            assert approve(client, market_headers, seller_refund_path).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail_commit)
    if phase == "approval":
        record = paypal_client.get(refund_path, headers=buyer_headers).json()
        assert record["state"] == "requested" and record["decision"] is None
        assert fake_gateway.refund_calls == []
    else:
        with Session(paypal_client.app.state.engine) as db, db.begin():
            row = db.get(RefundRequest, refund_request["id"])
            assert row.state == "refund_pending" and row.provider_refund_id
            row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        with TestClient(create_app(market_url, paypal_gateway=fake_gateway)) as restarted:
            result = restarted.post(refund_path + "/reconcile", headers=buyer_headers, json={})
            assert result.status_code == 200 and result.json()["state"] == "refunded"
        assert len(fake_gateway.refund_calls) == 1


def test_retry_window_never_creates_a_fresh_refund_key(
    paypal_client,
    fake_gateway,
    market_headers,
    refund_request,
    seller_refund_path,
    monkeypatch,
):
    fake_gateway.refund_behavior = "timeout_before"
    assert approve(paypal_client, market_headers, seller_refund_path).status_code == 502
    monkeypatch.setattr(service, "utcnow", lambda: datetime.now(UTC) + timedelta(hours=7))
    result = approve(paypal_client, market_headers, seller_refund_path)
    assert (
        result.status_code == 409
        and result.json()["detail"]["code"] == "REFUND_RETRY_WINDOW_ELAPSED"
    )
    assert len(fake_gateway.refund_calls) == 1


def test_metadata_migration_preserves_financial_history_and_blocks_record_loss(
    paypal_client,
    buyer_headers,
    refund_path,
    refund_request,
):
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    engine = paypal_client.app.state.engine
    with engine.connect() as connection:
        before = connection.execute(text("SELECT * FROM paypal_checkouts ORDER BY order_id")).all()
    command.check(config)
    with pytest.raises(RuntimeError, match="refund records"):
        command.downgrade(config, "0009")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT * FROM paypal_checkouts ORDER BY order_id")).all()
            == before
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    assert paypal_client.get(refund_path, headers=buyer_headers).json() == refund_request
    schema = paypal_client.get("/openapi.json").json()
    seller = schema["paths"]["/api/v1/seller/orders/{order_id}/refund-request/approve"]["post"]
    assert seller["security"] == [{"HTTPBearer": []}]
    assert {"401", "403", "404", "409", "422", "502", "503"} <= set(seller["responses"])
