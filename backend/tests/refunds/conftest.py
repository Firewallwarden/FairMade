"""Synthetic refund provider and a paid order; all external effects are mocked."""

from copy import deepcopy

import pytest
from payment_fixtures import FakeGateway

from fairmade.orders.domain import money
from fairmade.payments.errors import ProviderError
from fairmade.payments.gateway import BASE_URL


class FakeRefundGateway(FakeGateway):
    def __init__(self):
        super().__init__()
        self.refunds = {}
        self.refund_keys = {}
        self.refund_calls = []
        self.refund_behavior = "success"
        self.refund_fetch_error = False
        self.capture_override = None

    def _capture(self, capture_id):
        for order in self.orders.values():
            unit = order["purchase_units"][0]
            for capture in unit.get("payments", {}).get("captures", []):
                if capture["id"] == capture_id:
                    return order, unit, capture
        raise ProviderError()

    def fetch_capture(self, capture_id):
        order, unit, capture = self._capture(capture_id)
        result = {
            "id": capture_id,
            "status": capture["status"],
            "amount": deepcopy(capture["amount"]),
            "payee": deepcopy(unit["payee"]),
            "supplementary_data": {"related_ids": {"order_id": order["id"]}},
        }
        if self.capture_override:
            self.capture_override(result)
        return result

    def refund(self, capture_id, refund_request_id, amount_minor, request_id):
        self.refund_calls.append((capture_id, refund_request_id, amount_minor, request_id))
        if request_id in self.refund_keys:
            return self.refund_keys[request_id]
        if self.refund_behavior == "timeout_before":
            raise ProviderError()
        remote_id = "REFUND" + str(len(self.refunds) + 1).zfill(10)
        status = {"pending": "PENDING", "failed": "FAILED"}.get(self.refund_behavior, "COMPLETED")
        self.refunds[remote_id] = {
            "id": remote_id,
            "status": status,
            "amount": {"currency_code": "USD", "value": str(money(amount_minor).amount)},
            "invoice_id": "fairmade-refund-" + refund_request_id,
            "custom_id": refund_request_id,
            "payer": {"email_address": "PRIVATE_REFUND_PAYER@example.com"},
            "links": [
                {
                    "rel": "up",
                    "method": "GET",
                    "href": BASE_URL + "/v2/payments/captures/" + capture_id,
                }
            ],
        }
        self.refund_keys[request_id] = remote_id
        if status == "COMPLETED":
            self._capture(capture_id)[2]["status"] = "REFUNDED"
        if self.refund_behavior == "unreachable_after":
            self.refund_fetch_error = True
            raise ProviderError()
        if self.refund_behavior == "timeout_after":
            raise ProviderError()
        return remote_id

    def fetch_refund(self, refund_id):
        if self.refund_fetch_error:
            raise ProviderError()
        return deepcopy(self.refunds[refund_id])


@pytest.fixture
def fake_gateway():
    return FakeRefundGateway()


@pytest.fixture
def paid_order(paypal_client, fake_gateway, buyer_headers, unpaid_order, checkout_path, checkout):
    fake_gateway.approve(checkout["provider_order_id"])
    result = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert result.status_code == 200 and result.json()["state"] == "completed", result.text
    return unpaid_order


@pytest.fixture
def refund_path(paid_order):
    return "/api/v1/orders/" + paid_order["id"] + "/refund-request"


@pytest.fixture
def seller_refund_path(refund_path):
    return refund_path.replace("/api/v1/orders/", "/api/v1/seller/orders/")


@pytest.fixture
def refund_request(paypal_client, buyer_headers, refund_path):
    result = paypal_client.post(
        refund_path, headers=buyer_headers, json={"reason": "Synthetic buyer refund reason"}
    )
    assert result.status_code == 201, result.text
    return result.json()
