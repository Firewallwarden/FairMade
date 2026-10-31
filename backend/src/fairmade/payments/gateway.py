"""Provider port and sandbox-only HTTP adapter; no database or browser dependencies."""

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

import httpx

from fairmade.orders.domain import money
from fairmade.payments.config import SandboxSettings, load_settings
from fairmade.payments.errors import ProviderError

BASE_URL = "https://api-m.sandbox.paypal.com"
PROVIDER_ID = re.compile(r"[A-Z0-9]{10,64}")


class Gateway(Protocol):
    merchant_id: str
    client_id: str

    def create(self, order_id: str, amount_minor: int, request_id: str) -> str: ...
    def capture(self, provider_id: str, request_id: str) -> None: ...
    def fetch(self, provider_id: str) -> dict: ...


def provider_id(value) -> str:
    if not isinstance(value, str) or not PROVIDER_ID.fullmatch(value):
        raise ProviderError()
    return value


class PayPalSandboxGateway:
    def __init__(self, settings: SandboxSettings, *, transport=None):
        self.merchant_id = settings.merchant_id
        self.client_id = settings.client_id
        self._secret = settings.client_secret
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=httpx.Timeout(10),
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _json(self, method, path, **kwargs) -> dict:
        try:
            # Bound memory consumption and reject redirects/unexpected response bodies.
            with self._client.stream(method, path, **kwargs) as response:
                if response.status_code not in (200, 201):
                    raise ProviderError()
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 262_144:
                        raise ProviderError()
                    chunks.append(chunk)
                result = json.loads(b"".join(chunks))
                if not isinstance(result, dict):
                    raise ProviderError()
                return result
        except (httpx.HTTPError, ValueError, UnicodeError) as exc:
            raise ProviderError() from exc

    def _headers(self, request_id=None) -> dict:
        token = self._json(
            "POST",
            "/v1/oauth2/token",
            auth=(self.client_id, self._secret.get_secret_value()),
            data={"grant_type": "client_credentials"},
        ).get("access_token")
        if not isinstance(token, str) or not token or len(token) > 8192:
            raise ProviderError()
        headers = {"Authorization": "Bearer " + token, "Prefer": "return=representation"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        return headers

    def create(self, order_id: str, amount_minor: int, request_id: str) -> str:
        result = self._json(
            "POST",
            "/v2/checkout/orders",
            headers=self._headers(request_id),
            json={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": order_id,
                        "custom_id": order_id,
                        "invoice_id": "fairmade-" + order_id,
                        "payee": {"merchant_id": self.merchant_id},
                        "amount": {
                            "currency_code": "USD",
                            "value": str(money(amount_minor).amount),
                        },
                        "description": "FairMade sandbox merchandise order",
                    }
                ],
                "application_context": {"shipping_preference": "NO_SHIPPING"},
            },
        )
        return provider_id(result.get("id"))

    def capture(self, provider_order_id: str, request_id: str) -> None:
        self._json(
            "POST",
            "/v2/checkout/orders/" + provider_id(provider_order_id) + "/capture",
            headers=self._headers(request_id),
            json={},
        )

    def fetch(self, provider_order_id: str) -> dict:
        return self._json(
            "GET",
            "/v2/checkout/orders/" + provider_id(provider_order_id),
            headers=self._headers(),
        )

    def refund(
        self,
        capture_id: str,
        refund_request_id: str,
        amount_minor: int,
        request_id: str,
    ) -> str:
        result = self._json(
            "POST",
            "/v2/payments/captures/" + provider_id(capture_id) + "/refund",
            headers=self._headers(request_id),
            json={
                "amount": {"currency_code": "USD", "value": str(money(amount_minor).amount)},
                "invoice_id": "fairmade-refund-" + refund_request_id,
                "custom_id": refund_request_id,
                "note_to_payer": "FairMade approved sandbox refund",
            },
        )
        return provider_id(result.get("id"))

    def fetch_capture(self, capture_id: str) -> dict:
        return self._json(
            "GET",
            "/v2/payments/captures/" + provider_id(capture_id),
            headers=self._headers(),
        )

    def fetch_refund(self, refund_id: str) -> dict:
        return self._json(
            "GET",
            "/v2/payments/refunds/" + provider_id(refund_id),
            headers=self._headers(),
        )


@contextmanager
def configured_gateway(injected: Gateway | None = None) -> Iterator[Gateway | None]:
    if injected is not None:
        yield injected
        return
    settings = load_settings()
    gateway = PayPalSandboxGateway(settings) if settings else None
    try:
        yield gateway
    finally:
        if gateway:
            gateway.close()
