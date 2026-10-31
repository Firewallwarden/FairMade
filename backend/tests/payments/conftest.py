"""A deterministic provider double: no credentials or external calls."""

from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

import pytest

from fairmade.orders.domain import money
from fairmade.payments.errors import ProviderError


class FakeGateway:
    merchant_id = "ABCDEFGHIJKLM"
    client_id = "public-synthetic-sandbox-client"

    def __init__(self):
        self.orders = {}
        self.keys = {}
        self.create_calls = []
        self.capture_calls = []
        self.fetch_error = False
        self.capture_behavior = "success"

    def create(self, order_id, amount_minor, request_id):
        self.create_calls.append((order_id, amount_minor, request_id))
        if request_id in self.keys:
            return self.keys[request_id]
        remote_id = "PAYPALORDER" + str(len(self.orders) + 1).zfill(8)
        self.keys[request_id] = remote_id
        self.orders[remote_id] = {
            "id": remote_id,
            "intent": "CAPTURE",
            "status": "CREATED",
            "payer": {"email_address": "PRIVATE_PAYER@example.com"},
            "purchase_units": [
                {
                    "reference_id": order_id,
                    "custom_id": order_id,
                    "invoice_id": "fairmade-" + order_id,
                    "amount": {"currency_code": "USD", "value": str(money(amount_minor).amount)},
                    "payee": {
                        "merchant_id": self.merchant_id,
                        "email_address": "PRIVATE_MERCHANT@example.com",
                    },
                }
            ],
        }
        return remote_id

    def approve(self, remote_id):
        self.orders[remote_id]["status"] = "APPROVED"

    def capture(self, remote_id, request_id):
        self.capture_calls.append((remote_id, request_id))
        if self.capture_behavior == "timeout_before":
            raise ProviderError()
        data = self.orders[remote_id]
        unit = data["purchase_units"][0]
        data["status"] = "COMPLETED"
        status = {"pending": "PENDING", "declined": "DECLINED"}.get(
            self.capture_behavior, "COMPLETED"
        )
        gross = int(Decimal(unit["amount"]["value"]) * 100)
        fee = min(gross, 100)
        unit["payments"] = {
            "captures": [
                {
                    "id": "CAPTURE" + remote_id[-8:],
                    "status": status,
                    "amount": deepcopy(unit["amount"]),
                    "final_capture": True,
                    "seller_receivable_breakdown": {
                        "gross_amount": deepcopy(unit["amount"]),
                        "paypal_fee": {"currency_code": "USD", "value": str(money(fee).amount)},
                        "net_amount": {
                            "currency_code": "USD",
                            "value": str(money(gross - fee).amount),
                        },
                    },
                }
            ]
        }
        if self.capture_behavior == "timeout_after":
            raise ProviderError()
        if self.capture_behavior == "unreachable_after":
            self.fetch_error = True
            raise ProviderError()

    def fetch(self, remote_id):
        if self.fetch_error:
            raise ProviderError()
        return deepcopy(self.orders[remote_id])


@pytest.fixture
def fake_gateway():
    return FakeGateway()


@pytest.fixture
def paypal_client(market_client, fake_gateway):
    market_client.app.state.paypal_gateway = fake_gateway
    return market_client


@pytest.fixture
def unpaid_order(paypal_client, buyer_headers, cart):
    result = paypal_client.post(
        "/api/v1/orders",
        headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
        json=cart,
    )
    assert result.status_code == 201, result.text
    return result.json()


@pytest.fixture
def checkout_path(unpaid_order):
    return "/api/v1/orders/" + unpaid_order["id"] + "/paypal-checkout"


@pytest.fixture
def checkout(paypal_client, buyer_headers, checkout_path):
    response = paypal_client.post(checkout_path, headers=buyer_headers, json={})
    assert response.status_code == 200, response.text
    return response.json()
