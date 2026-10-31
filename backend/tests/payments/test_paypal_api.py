"""Payment integrity, ownership, retry/crash recovery and stock settlement."""

import json
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import PayPalCheckout
from fairmade.payments import service


def inventory(client, seller_headers, source):
    return client.get(source["path"] + "/inventory", headers=seller_headers).json()


def approve(fake, checkout):
    fake.approve(checkout["provider_order_id"])


def test_verified_capture_confirms_paid_and_consumes_stock_once(
    paypal_client,
    fake_gateway,
    buyer_headers,
    market_headers,
    order_source,
    unpaid_order,
    checkout_path,
    checkout,
):
    assert checkout["environment"] == "sandbox" and checkout["merchant_mode"] == "shared"
    assert checkout["amount"] == {"currency": "USD", "amount": "34.00"}
    approve(fake_gateway, checkout)
    paid = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert paid.status_code == 200, paid.text
    result = paid.json()
    assert result["state"] == "completed" and result["capture_id"]
    assert result["sandbox_fee"]["amount"] == "1.00"
    assert result["sandbox_net"]["amount"] == "33.00"
    assert result["verified_at"].endswith("Z")
    assert "PRIVATE_" not in json.dumps(result) and "payer" not in result
    stock = inventory(paypal_client, market_headers, order_source)
    assert (stock["on_hand"], stock["reserved"], stock["available"], stock["revision"]) == (
        8,
        0,
        8,
        2,
    )
    order_path = "/api/v1/orders/" + unpaid_order["id"]
    order = paypal_client.get(order_path, headers=buyer_headers).json()
    assert order["status"] == "paid" and order["snapshot"] == unpaid_order["snapshot"]
    repeated = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert repeated.json() == result and len(fake_gateway.capture_calls) == 1
    assert paypal_client.post(checkout_path, headers=buyer_headers, json={}).json() == result
    assert paypal_client.post(order_path + "/cancel", headers=buyer_headers).status_code == 409
    seller_receipt = paypal_client.get(
        "/api/v1/seller/orders/" + unpaid_order["id"] + "/paypal-checkout",
        headers=market_headers,
    )
    assert seller_receipt.json() == result


def test_create_is_idempotent_and_approval_is_not_payment(
    paypal_client,
    fake_gateway,
    buyer_headers,
    checkout_path,
    checkout,
    unpaid_order,
):
    assert paypal_client.post(checkout_path, headers=buyer_headers, json={}).json() == checkout
    assert len(fake_gateway.create_calls) == 1
    unapproved = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert unapproved.status_code == 409
    assert unapproved.json()["detail"]["code"] == "PAYPAL_APPROVAL_REQUIRED"
    approve(fake_gateway, checkout)
    reconciled = paypal_client.post(checkout_path + "/reconcile", headers=buyer_headers, json={})
    assert reconciled.json()["state"] == "ready"
    assert (
        paypal_client.get("/api/v1/orders/" + unpaid_order["id"], headers=buyer_headers).json()[
            "status"
        ]
        == "pending_payment"
    )
    assert fake_gateway.capture_calls == []


@pytest.mark.parametrize(
    "behavior,expected",
    [
        ("success", "completed"),
        ("timeout_after", "completed"),
        ("pending", "capture_pending"),
        ("declined", "failed"),
    ],
)
def test_capture_results_are_verified_not_assumed(
    paypal_client,
    fake_gateway,
    buyer_headers,
    market_headers,
    order_source,
    checkout_path,
    checkout,
    behavior,
    expected,
):
    approve(fake_gateway, checkout)
    fake_gateway.capture_behavior = behavior
    response = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert response.status_code == 200 and response.json()["state"] == expected
    stock = inventory(paypal_client, market_headers, order_source)
    assert stock["on_hand"] == (8 if expected == "completed" else 10)
    assert stock["reserved"] == (2 if expected == "capture_pending" else 0)


def test_unknown_capture_keeps_hold_past_deadline_then_reconciles(
    paypal_client,
    fake_gateway,
    buyer_headers,
    market_headers,
    order_source,
    unpaid_order,
    checkout_path,
    checkout,
    monkeypatch,
):
    approve(fake_gateway, checkout)
    fake_gateway.capture_behavior = "unreachable_after"
    response = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert response.status_code == 502
    future = datetime.fromisoformat(unpaid_order["expires_at"]) + timedelta(hours=1)
    from fairmade.inventory import service as inventory_service

    monkeypatch.setattr(inventory_service, "utcnow", lambda: future)
    monkeypatch.setattr(service, "utcnow", lambda: future)
    assert inventory(paypal_client, market_headers, order_source)["reserved"] == 2
    assert (
        paypal_client.post(
            "/api/v1/orders/" + unpaid_order["id"] + "/cancel", headers=buyer_headers
        ).status_code
        == 409
    )
    fake_gateway.fetch_error = False
    recovered = paypal_client.post(checkout_path + "/reconcile", headers=buyer_headers, json={})
    assert recovered.status_code == 200 and recovered.json()["state"] == "completed"
    assert inventory(paypal_client, market_headers, order_source)["on_hand"] == 8
    assert len(fake_gateway.capture_calls) == 1


def test_capture_retry_reuses_key_after_network_failure(
    paypal_client,
    fake_gateway,
    buyer_headers,
    checkout_path,
    checkout,
):
    approve(fake_gateway, checkout)
    fake_gateway.capture_behavior = "timeout_before"
    assert (
        paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={}).status_code
        == 502
    )
    fake_gateway.capture_behavior = "success"
    assert (
        paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={}).json()[
            "state"
        ]
        == "completed"
    )
    assert fake_gateway.capture_calls[0] == fake_gateway.capture_calls[1]


def test_retry_window_prevents_late_new_capture(
    paypal_client,
    fake_gateway,
    buyer_headers,
    checkout_path,
    checkout,
    monkeypatch,
):
    approve(fake_gateway, checkout)
    fake_gateway.capture_behavior = "timeout_before"
    assert (
        paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={}).status_code
        == 502
    )
    future = datetime.now(UTC) + timedelta(hours=7)
    monkeypatch.setattr(service, "utcnow", lambda: future)
    response = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert (
        response.status_code == 409
        and response.json()["detail"]["code"] == "PAYPAL_RECONCILE_REQUIRED"
    )
    assert len(fake_gateway.capture_calls) == 1


@pytest.mark.parametrize(
    "bad_field",
    [
        "amount",
        "currency",
        "merchant",
        "reference",
        "invoice",
        "custom",
        "intent",
        "id",
        "capture_amount",
        "capture_state",
        "fee",
        "multiple_units",
        "multiple_captures",
    ],
)
def test_mismatched_provider_data_never_marks_paid(
    paypal_client,
    fake_gateway,
    buyer_headers,
    market_headers,
    order_source,
    unpaid_order,
    checkout_path,
    checkout,
    bad_field,
):
    approve(fake_gateway, checkout)
    remote = fake_gateway.orders[checkout["provider_order_id"]]
    unit = remote["purchase_units"][0]
    if bad_field.startswith("capture") or bad_field in ("fee", "multiple_captures"):
        fake_gateway.capture(checkout["provider_order_id"], str(uuid4()))
        if bad_field == "capture_amount":
            unit["payments"]["captures"][0]["amount"]["value"] = "0.01"
        elif bad_field == "capture_state":
            unit["payments"]["captures"][0]["status"] = "REFUNDED"
        elif bad_field == "fee":
            unit["payments"]["captures"][0]["seller_receivable_breakdown"]["paypal_fee"][
                "value"
            ] = "0.01"
        else:
            unit["payments"]["captures"] *= 2
    elif bad_field == "amount":
        unit["amount"]["value"] = "0.01"
    elif bad_field == "currency":
        unit["amount"]["currency_code"] = "EUR"
    elif bad_field == "merchant":
        unit["payee"]["merchant_id"] = "OTHER"
    elif bad_field in ("reference", "invoice", "custom"):
        unit[bad_field + "_id"] = "OTHER"
    elif bad_field == "intent":
        remote["intent"] = "AUTHORIZE"
    elif bad_field == "id":
        remote["id"] = "OTHER"
    else:
        remote["purchase_units"] *= 2
    response = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "PAYPAL_VERIFICATION_FAILED"
    assert (
        paypal_client.get("/api/v1/orders/" + unpaid_order["id"], headers=buyer_headers).json()[
            "status"
        ]
        == "payment_review"
    )
    stock = inventory(paypal_client, market_headers, order_source)
    assert stock["on_hand"] == 10 and stock["reserved"] == 2


def test_missing_fee_information_is_not_invented(
    paypal_client,
    fake_gateway,
    buyer_headers,
    checkout_path,
    checkout,
):
    approve(fake_gateway, checkout)
    fake_gateway.capture(checkout["provider_order_id"], str(uuid4()))
    del fake_gateway.orders[checkout["provider_order_id"]]["purchase_units"][0]["payments"][
        "captures"
    ][0]["seller_receivable_breakdown"]
    result = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert result.status_code == 200 and result.json()["state"] == "completed"
    assert "sandbox_fee" not in result.json() and "sandbox_net" not in result.json()


def test_ownership_and_body_validation(
    paypal_client,
    market_account,
    buyer_headers,
    market_headers,
    checkout_path,
    checkout,
):
    other = market_account("unrelated-buyer@example.com", roles=())
    for suffix in ("", "/capture", "/reconcile"):
        assert paypal_client.post(checkout_path + suffix, headers=other, json={}).status_code == 404
        assert paypal_client.post(checkout_path + suffix, json={}).status_code == 401
        assert (
            paypal_client.post(
                checkout_path + suffix, headers=buyer_headers, json={"amount": "0.01"}
            ).status_code
            == 422
        )
    assert paypal_client.get(checkout_path, headers=other).status_code == 404
    assert paypal_client.get(checkout_path).status_code == 401
    seller_path = checkout_path.replace("/api/v1/orders/", "/api/v1/seller/orders/")
    assert paypal_client.get(seller_path, headers=buyer_headers).status_code == 403
    assert paypal_client.get(seller_path, headers=market_headers).status_code == 200
    other_seller = market_account("unrelated-seller@example.com")
    assert (
        paypal_client.post(seller_path + "/reconcile", headers=other_seller, json={}).status_code
        == 404
    )


def test_expired_or_changed_order_cannot_start_capture(
    paypal_client,
    fake_gateway,
    buyer_headers,
    market_headers,
    order_source,
    checkout_path,
    checkout,
    unpaid_order,
):
    approve(fake_gateway, checkout)
    assert (
        paypal_client.post(
            order_source["path"] + "/listing/deactivate", headers=market_headers
        ).status_code
        == 204
    )
    response = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert (
        response.status_code == 409 and response.json()["detail"]["code"] == "ORDER_LISTING_CHANGED"
    )
    assert fake_gateway.capture_calls == []
    assert (
        paypal_client.post(
            "/api/v1/orders/" + unpaid_order["id"] + "/cancel", headers=buyer_headers
        ).status_code
        == 200
    )


def test_concurrent_capture_does_not_hold_database_during_network_io(
    paypal_client,
    fake_gateway,
    buyer_headers,
    market_headers,
    market_url,
    order_source,
    checkout_path,
    checkout,
):
    approve(fake_gateway, checkout)
    entered, resume = Event(), Event()
    original_capture = fake_gateway.capture
    app = create_app(market_url, paypal_gateway=fake_gateway)

    def slow_capture(remote_id, request_id):
        entered.set()
        assert resume.wait(timeout=10)
        original_capture(remote_id, request_id)

    fake_gateway.capture = slow_capture
    results = []

    def submit():
        with TestClient(app) as client:
            results.append(client.post(checkout_path + "/capture", headers=buyer_headers, json={}))

    worker = Thread(target=submit)
    worker.start()
    try:
        assert entered.wait(timeout=10)
        repeated = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
        assert repeated.status_code == 409
        # A stock update can acquire SQLite's writer while the provider is waiting.
        stock = inventory(paypal_client, market_headers, order_source)
        assert (
            paypal_client.put(
                order_source["path"] + "/inventory",
                headers=market_headers,
                json={
                    "expected_revision": stock["revision"],
                    "selling_unit": "loaf",
                    "on_hand": 12,
                },
            ).status_code
            == 200
        )
    finally:
        resume.set()
        worker.join(timeout=15)
    assert results and results[0].status_code == 200
    assert len(fake_gateway.capture_calls) == 1
    assert inventory(paypal_client, market_headers, order_source)["on_hand"] == 10


def test_remote_success_local_commit_failure_recovers_after_restart(
    paypal_client,
    fake_gateway,
    buyer_headers,
    market_headers,
    market_url,
    order_source,
    checkout_path,
    checkout,
):
    approve(fake_gateway, checkout)

    def fail_final_commit(db):
        if any(isinstance(obj, PayPalCheckout) and obj.state == "completed" for obj in db.dirty):
            raise RuntimeError("Synthetic settlement write failure")

    event.listen(Session, "before_commit", fail_final_commit)
    try:
        with TestClient(
            create_app(market_url, paypal_gateway=fake_gateway), raise_server_exceptions=False
        ) as client:
            assert (
                client.post(checkout_path + "/capture", headers=buyer_headers, json={}).status_code
                == 500
            )
    finally:
        event.remove(Session, "before_commit", fail_final_commit)
    assert inventory(paypal_client, market_headers, order_source)["on_hand"] == 10
    with Session(paypal_client.app.state.engine) as db, db.begin():
        payment = db.get(PayPalCheckout, checkout["order_id"])
        assert payment.state == "capture_pending"
        payment.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    seller_path = checkout_path.replace("/api/v1/orders/", "/api/v1/seller/orders/")
    with TestClient(create_app(market_url, paypal_gateway=fake_gateway)) as restarted:
        recovered = restarted.post(seller_path + "/reconcile", headers=market_headers, json={})
        assert recovered.status_code == 200 and recovered.json()["state"] == "completed"
    assert inventory(paypal_client, market_headers, order_source)["on_hand"] == 8
    assert len(fake_gateway.capture_calls) == 1


def test_disabled_config_and_buyer_cors(market_url, buyer_headers, unpaid_order, monkeypatch):
    monkeypatch.setenv("FAIRMADE_CORS_ORIGINS", "http://localhost:5173")
    with TestClient(create_app(market_url)) as client:
        config = client.get("/api/v1/paypal/config").json()
        assert config == {
            "enabled": False,
            "environment": "sandbox",
            "merchant_mode": "shared",
            "currency": "USD",
        }
        path = "/api/v1/orders/" + unpaid_order["id"] + "/paypal-checkout"
        assert client.post(path, headers=buyer_headers, json={}).status_code == 503
        cors = client.options(
            "/api/v1/orders",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
            },
        )
        assert cors.status_code == 200


def test_create_recovers_unknown_provider_result_with_same_idempotency_key(
    paypal_client,
    fake_gateway,
    buyer_headers,
    checkout_path,
):
    original = fake_gateway.create
    calls = 0

    def uncertain(*args):
        nonlocal calls
        result = original(*args)
        calls += 1
        if calls == 1:
            from fairmade.payments.errors import ProviderError

            raise ProviderError()
        return result

    fake_gateway.create = uncertain
    assert paypal_client.post(checkout_path, headers=buyer_headers, json={}).status_code == 502
    response = paypal_client.post(checkout_path, headers=buyer_headers, json={})
    assert response.status_code == 200 and response.json()["state"] == "ready"
    assert len(fake_gateway.orders) == 1
    assert fake_gateway.create_calls[0][2] == fake_gateway.create_calls[1][2]


def test_expired_order_and_merchant_switch_are_rejected(
    paypal_client,
    fake_gateway,
    buyer_headers,
    checkout_path,
    checkout,
    unpaid_order,
    monkeypatch,
):
    fake_gateway.merchant_id = "MNOPQRSTUVWXY"
    result = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert (
        result.status_code == 503 and result.json()["detail"]["code"] == "PAYPAL_MERCHANT_CHANGED"
    )
    fake_gateway.merchant_id = "ABCDEFGHIJKLM"
    monkeypatch.setattr(
        service, "utcnow", lambda: datetime.fromisoformat(unpaid_order["expires_at"])
    )
    assert (
        paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={}).status_code
        == 409
    )
    assert fake_gateway.capture_calls == []


def test_migration_preserves_orders_and_blocks_destructive_receipt_downgrade(
    paypal_client,
    buyer_headers,
    checkout_path,
    checkout,
):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    engine = paypal_client.app.state.engine
    with engine.connect() as connection:
        before = connection.execute(text("SELECT * FROM orders ORDER BY id")).all()
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="payment records"):
        command.downgrade(config, "0008")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT * FROM orders ORDER BY id")).all() == before
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    assert paypal_client.get(checkout_path, headers=buyer_headers).json() == checkout


@pytest.mark.parametrize("value", ["34", "34.0", "34.00"])
def test_exact_usd_format_variants_are_supported(
    paypal_client,
    fake_gateway,
    buyer_headers,
    checkout_path,
    checkout,
    value,
):
    remote = fake_gateway.orders[checkout["provider_order_id"]]
    remote["purchase_units"][0]["amount"]["value"] = value
    approve(fake_gateway, checkout)
    result = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert result.status_code == 200 and result.json()["state"] == "completed"


def test_payment_validation_does_not_echo_arbitrary_sensitive_input(
    paypal_client,
    buyer_headers,
    checkout_path,
):
    result = paypal_client.post(
        checkout_path, headers=buyer_headers, json={"unsupported": "PRIVATE_INPUT_CANARY"}
    )
    assert result.status_code == 422 and "PRIVATE_INPUT_CANARY" not in result.text
