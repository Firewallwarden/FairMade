"""The refund adapter uses fixed sandbox paths and server-chosen full amounts."""

import json

import httpx
import pytest
from pydantic import SecretStr

from fairmade.payments.config import SandboxSettings
from fairmade.payments.errors import ProviderError
from fairmade.payments.gateway import PayPalSandboxGateway


def test_refund_adapter_preserves_amount_key_and_request_correlation():
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.host == "api-m.sandbox.paypal.com"
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "synthetic-oauth-token"})
        assert request.headers["Authorization"] == "Bearer synthetic-oauth-token"
        if request.method == "POST":
            assert request.url.path == "/v2/payments/captures/CAPTURE000001/refund"
            assert request.headers["PayPal-Request-Id"] == "durable-refund-key"
            body = json.loads(request.content)
            assert body == {
                "amount": {"currency_code": "USD", "value": "34.00"},
                "invoice_id": "fairmade-refund-request-id",
                "custom_id": "request-id",
                "note_to_payer": "FairMade approved sandbox refund",
            }
            return httpx.Response(201, json={"id": "REFUND00000001"})
        return httpx.Response(200, json={"id": "REFUND00000001"})

    adapter = PayPalSandboxGateway(
        SandboxSettings("synthetic-client", SecretStr("synthetic-secret"), "ABCDEFGHIJKLM"),
        transport=httpx.MockTransport(respond),
    )
    try:
        assert (
            adapter.refund("CAPTURE000001", "request-id", 3400, "durable-refund-key")
            == "REFUND00000001"
        )
        adapter.fetch_capture("CAPTURE000001")
        adapter.fetch_refund("REFUND00000001")
        assert len(calls) == 6
        assert calls[-1].url.path == "/v2/payments/refunds/REFUND00000001"
    finally:
        adapter.close()


def test_refund_ids_cannot_inject_provider_paths():
    adapter = PayPalSandboxGateway(
        SandboxSettings("synthetic-client", SecretStr("synthetic-secret"), "ABCDEFGHIJKLM"),
        transport=httpx.MockTransport(lambda _request: pytest.fail("No HTTP request expected")),
    )
    try:
        with pytest.raises(ProviderError):
            adapter.refund("../token", "request-id", 3400, "key")
        with pytest.raises(ProviderError):
            adapter.fetch_refund("../token")
    finally:
        adapter.close()
