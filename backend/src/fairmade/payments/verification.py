"""Strict, deterministic validation of server-fetched PayPal order data."""

import re
from dataclasses import dataclass

from fairmade.payments.errors import VerificationError
from fairmade.payments.money import parse_usd_minor

IDENTIFIER = re.compile(r"[A-Z0-9]{10,64}")


@dataclass(frozen=True)
class VerifiedPayment:
    provider_status: str
    outcome: str
    capture_id: str | None = None
    fee_minor: int | None = None
    net_minor: int | None = None


def _minor(value: dict) -> int:
    return parse_usd_minor(value)


def _verify(data: dict, order_id: str, remote_id: str, merchant_id: str, expected: int):
    if data["id"] != remote_id or data["intent"] != "CAPTURE":
        raise VerificationError()
    units = data["purchase_units"]
    if not isinstance(units, list) or len(units) != 1:
        raise VerificationError()
    unit = units[0]
    if (
        unit["reference_id"] != order_id
        or unit["custom_id"] != order_id
        or unit["invoice_id"] != "fairmade-" + order_id
        or unit["payee"]["merchant_id"] != merchant_id
        or _minor(unit["amount"]) != expected
    ):
        raise VerificationError()
    status = data["status"]
    if status not in (
        "CREATED",
        "SAVED",
        "APPROVED",
        "PAYER_ACTION_REQUIRED",
        "COMPLETED",
        "VOIDED",
    ):
        raise VerificationError()
    captures = unit.get("payments", {}).get("captures", [])
    if captures:
        if not isinstance(captures, list) or len(captures) != 1:
            raise VerificationError()
        capture = captures[0]
        capture_id = capture["id"]
        if not isinstance(capture_id, str) or not IDENTIFIER.fullmatch(capture_id):
            raise VerificationError()
        if _minor(capture["amount"]) != expected or capture.get("final_capture") is not True:
            raise VerificationError()
        if capture["status"] == "PENDING":
            return VerifiedPayment(status, "pending")
        if capture["status"] in ("DECLINED", "FAILED"):
            return VerifiedPayment(status, "failed")
        if status != "COMPLETED" or capture["status"] != "COMPLETED":
            raise VerificationError()
        breakdown = capture.get("seller_receivable_breakdown")
        fee = net = None
        if breakdown is not None:
            if (
                "gross_amount" in breakdown and _minor(breakdown["gross_amount"]) != expected
            ) or breakdown.get("platform_fees"):
                raise VerificationError()
            fee = _minor(breakdown["paypal_fee"]) if "paypal_fee" in breakdown else None
            net = _minor(breakdown["net_amount"]) if "net_amount" in breakdown else None
            if (
                (fee is not None and fee > expected)
                or (net is not None and net > expected)
                or (fee is not None and net is not None and fee + net != expected)
            ):
                raise VerificationError()
        return VerifiedPayment(status, "paid", capture_id, fee, net)
    if status == "VOIDED":
        return VerifiedPayment(status, "failed")
    if status not in ("CREATED", "SAVED", "APPROVED", "PAYER_ACTION_REQUIRED"):
        raise VerificationError()
    return VerifiedPayment(status, "ready")


def verify(
    data: dict, order_id: str, remote_id: str, merchant_id: str, expected: int
) -> VerifiedPayment:
    try:
        return _verify(data, order_id, remote_id, merchant_id, expected)
    except (KeyError, TypeError, ValueError, AttributeError, ArithmeticError) as exc:
        raise VerificationError() from exc
