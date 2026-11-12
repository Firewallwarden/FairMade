"""Opt-in human-approved real sandbox capture/refund, with retained local history."""

import os
import time
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from payments.sandbox_support import approval_url, wait_for_approval

from fairmade.payments.config import load_settings
from fairmade.payments.gateway import PayPalSandboxGateway

pytestmark = pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_SANDBOX_PAYMENT_EVAL") != "true",
    reason="Real sandbox transactions and human buyer approval are explicitly opt-in.",
)
BACKEND = Path(__file__).parents[2]


@pytest.fixture(autouse=True)
def disable_real_paypal():
    """Override the offline default only in this explicitly opted-in module."""
    assert os.environ.get("FAIRMADE_RUN_SANDBOX_PAYMENT_EVAL") == "true"
    assert load_settings() is not None, "Configure the server-only PayPal sandbox variables."


@pytest.fixture
def market_url(monkeypatch):
    assert load_settings() is not None, "Configure the server-only PayPal sandbox variables."
    directory = BACKEND / ".pytest_cache" / "paypal-sandbox" / str(uuid4())
    directory.mkdir(parents=True)
    assert directory.resolve().is_relative_to(BACKEND.resolve())
    url = "sqlite:///" + (directory / "history.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    print(f"SANDBOX_HISTORY retained at {directory}")
    return url


def test_real_sandbox_capture_and_seller_approved_refund(
    market_client, market_headers, buyer_headers, order_source, cart
):
    provider = market_client.app.state.paypal_gateway
    assert isinstance(provider, PayPalSandboxGateway), "A real sandbox adapter is required."
    created = market_client.post(
        "/api/v1/orders",
        headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
        json=cart,
    )
    assert created.status_code == 201
    order_path = "/api/v1/orders/" + created.json()["id"]
    path = order_path + "/paypal-checkout"
    response = market_client.post(path, headers=buyer_headers, json={})
    assert response.status_code == 200
    checkout = response.json()
    assert checkout["environment"] == "sandbox"
    assert checkout["amount"] == {"currency": "USD", "amount": "34.00"}
    assert market_client.post(path, headers=buyer_headers, json={}).json() == checkout

    remote = provider.fetch(checkout["provider_order_id"])
    link = approval_url(remote, checkout["provider_order_id"])
    handoff = BACKEND / ".pytest_cache" / "paypal-sandbox" / (str(uuid4()) + ".url")
    handoff.write_text("[InternetShortcut]\nURL=" + link + "\n", encoding="utf-8")
    print(f"SANDBOX_APPROVAL_REQUIRED open {handoff}", flush=True)
    wait_for_approval(provider.fetch, checkout["provider_order_id"])
    assert (
        market_client.get(order_path, headers=buyer_headers).json()["status"] == "pending_payment"
    )

    captured = market_client.post(path + "/capture", headers=buyer_headers, json={})
    assert captured.status_code == 200
    receipt = captured.json()
    assert (
        receipt["state"] == "completed" and receipt.get("verified_at") and receipt.get("capture_id")
    )
    assert market_client.post(path + "/capture", headers=buyer_headers, json={}).json() == receipt
    assert market_client.get(order_path, headers=buyer_headers).json()["status"] == "paid"
    stock_path = order_source["path"] + "/inventory"
    stock = market_client.get(stock_path, headers=market_headers).json()
    assert (stock["on_hand"], stock["reserved"], stock["available"]) == (8, 0, 8)

    refund_path = order_path + "/refund-request"
    requested = market_client.post(
        refund_path, headers=buyer_headers, json={"reason": "Synthetic verification refund"}
    )
    assert requested.status_code == 201 and requested.json()["state"] == "requested"
    assert market_client.get(order_path, headers=buyer_headers).json()["status"] == "paid"
    seller_path = "/api/v1/seller/orders/" + created.json()["id"] + "/refund-request"
    approved = market_client.post(
        seller_path + "/approve", headers=market_headers, json={"expected_revision": 1}
    )
    assert approved.status_code == 200
    refund = approved.json()
    deadline = time.monotonic() + 120
    while refund["state"] == "refund_pending" and time.monotonic() < deadline:
        time.sleep(3)
        reconciled = market_client.post(refund_path + "/reconcile", headers=buyer_headers, json={})
        assert reconciled.status_code == 200
        refund = reconciled.json()
    assert refund["state"] == "refunded" and refund.get("verified_at")
    assert refund.get("provider_refund_id") and refund["decision"] == "approved"
    assert (
        market_client.post(
            seller_path + "/approve", headers=market_headers, json={"expected_revision": 1}
        ).json()
        == refund
    )
    assert market_client.get(order_path, headers=buyer_headers).json()["status"] == "refunded"
    assert market_client.get(stock_path, headers=market_headers).json() == stock
    print("SANDBOX_VERIFIED capture, retry safety, seller-approved refund and unchanged stock")
