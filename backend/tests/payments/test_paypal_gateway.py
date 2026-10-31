"""Real HTTP adapter behavior with an in-memory transport; no network access."""

import json

import httpx
import pytest
from pydantic import SecretStr

from fairmade.payments.config import SandboxSettings, load_settings
from fairmade.payments.errors import ProviderError
from fairmade.payments.gateway import PayPalSandboxGateway

SETTINGS = SandboxSettings("synthetic-client", SecretStr("synthetic-secret"), "ABCDEFGHIJKLM")


def test_adapter_uses_sandbox_oauth_saved_totals_and_distinct_keys():
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.host == "api-m.sandbox.paypal.com"
        assert request.url.scheme == "https"
        if request.url.path == "/v1/oauth2/token":
            assert request.headers["Authorization"].startswith("Basic ")
            assert request.content == b"grant_type=client_credentials"
            return httpx.Response(200, json={"access_token": "synthetic-private-oauth-token"})
        assert request.headers["Authorization"] == "Bearer synthetic-private-oauth-token"
        if request.url.path == "/v2/checkout/orders":
            body = json.loads(request.content)
            assert body["intent"] == "CAPTURE"
            unit = body["purchase_units"][0]
            assert unit["amount"] == {"currency_code": "USD", "value": "34.00"}
            assert unit["payee"] == {"merchant_id": SETTINGS.merchant_id}
            assert unit["reference_id"] == unit["custom_id"] == "local-order"
            assert unit["invoice_id"] == "fairmade-local-order"
            assert body["application_context"]["shipping_preference"] == "NO_SHIPPING"
            assert request.headers["PayPal-Request-Id"] == "create-key"
        elif request.url.path.endswith("/capture"):
            assert request.headers["PayPal-Request-Id"] == "capture-key"
        return httpx.Response(
            201 if request.method == "POST" else 200, json={"id": "PAYPALORDER0001"}
        )

    adapter = PayPalSandboxGateway(SETTINGS, transport=httpx.MockTransport(respond))
    try:
        remote = adapter.create("local-order", 3400, "create-key")
        adapter.capture(remote, "capture-key")
        assert adapter.fetch(remote) == {"id": remote}
        assert len(calls) == 6
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"Location": "https://untrusted.example/"}),
        httpx.Response(500, text="synthetic-sensitive-provider-error"),
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json=[]),
        httpx.Response(200, content=b"x" * 262145),
    ],
)
def test_bad_provider_responses_fail_closed_without_echoing_body(response):
    calls = []

    def respond(request):
        calls.append(request)
        return response

    adapter = PayPalSandboxGateway(SETTINGS, transport=httpx.MockTransport(respond))
    try:
        with pytest.raises(ProviderError) as error:
            adapter.create("local-order", 3400, "key")
        assert str(error.value) == ""
        assert len(calls) == 1
    finally:
        adapter.close()


def test_provider_path_cannot_be_injected():
    adapter = PayPalSandboxGateway(
        SETTINGS, transport=httpx.MockTransport(lambda _r: pytest.fail("No request expected"))
    )
    try:
        with pytest.raises(ProviderError):
            adapter.fetch("../v1/oauth2/token")
    finally:
        adapter.close()


def test_config_requires_explicit_sandbox_credentials(monkeypatch):
    monkeypatch.setenv("FAIRMADE_PAYPAL_ENABLED", "true")
    for key in ("CLIENT_ID", "CLIENT_SECRET", "MERCHANT_ID"):
        monkeypatch.delenv("FAIRMADE_PAYPAL_SANDBOX_" + key, raising=False)
    with pytest.raises(ValueError):
        load_settings()
    monkeypatch.setenv("FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID", SETTINGS.client_id)
    monkeypatch.setenv("FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setenv("FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID", SETTINGS.merchant_id)
    assert load_settings() == SETTINGS
    assert "synthetic-secret" not in repr(load_settings())
    monkeypatch.setenv("FAIRMADE_PAYPAL_ENVIRONMENT", "live")
    with pytest.raises(ValueError, match="sandbox"):
        load_settings()
