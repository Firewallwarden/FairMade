"""Verify full-refund amount, request correlation and original capture binding."""

from urllib.parse import urlsplit

from fairmade.payments.errors import VerificationError
from fairmade.payments.money import parse_usd_minor


def capture_status(
    data: dict, capture_id: str, merchant_id: str, provider_order_id: str, amount_minor: int
) -> str:
    try:
        if (
            data["id"] != capture_id
            or data["payee"]["merchant_id"] != merchant_id
            or data["supplementary_data"]["related_ids"]["order_id"] != provider_order_id
            or parse_usd_minor(data["amount"]) != amount_minor
            or data["status"] not in ("COMPLETED", "REFUNDED", "PARTIALLY_REFUNDED")
        ):
            raise VerificationError()
        return data["status"]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise VerificationError() from exc


def refund_status(
    data: dict, refund_id: str, request_id: str, capture_id: str, amount_minor: int
) -> str:
    try:
        if (
            data["id"] != refund_id
            or data["invoice_id"] != "fairmade-refund-" + request_id
            or parse_usd_minor(data["amount"]) != amount_minor
            or data["status"] not in ("COMPLETED", "PENDING", "FAILED", "CANCELLED")
        ):
            raise VerificationError()
        parents = [link for link in data["links"] if link["rel"] == "up"]
        if len(parents) != 1 or parents[0].get("method") != "GET":
            raise VerificationError()
        parent = urlsplit(parents[0]["href"])
        if (
            parent.scheme != "https"
            or parent.hostname not in ("api-m.sandbox.paypal.com", "api.sandbox.paypal.com")
            or parent.port not in (None, 443)
            or parent.username is not None
            or parent.path != "/v2/payments/captures/" + capture_id
            or parent.query
            or parent.fragment
        ):
            raise VerificationError()
        # This link is compared only; no HTTP request ever follows provider links.
        return data["status"]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise VerificationError() from exc
