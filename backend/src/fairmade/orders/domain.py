"""Pure order arithmetic, canonical retry identity and deadline interpretation."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal, localcontext

from fairmade.orders.schemas import CartRequest
from fairmade.passports.schemas import PublicPrice

MAX_SUBTOTAL_MINOR = 100_000_000_000
NOTICES = [
    "This is an unpaid order draft, not a purchase or payment confirmation.",
    "Amounts cover merchandise only; shipping, taxes and delivery are not configured.",
    "Stock holds expire after 15 minutes and do not confirm delivery or seller claims.",
]


def money(minor: int) -> PublicPrice:
    with localcontext() as context:
        context.prec = 40
        return PublicPrice(amount=Decimal(minor).scaleb(-2).quantize(Decimal("0.01")))


def fingerprint(body: CartRequest) -> str:
    items = sorted(body.model_dump(mode="json")["items"], key=lambda item: item["listing_id"])
    encoded = json.dumps(items, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def effective_status(
    status: str,
    expires_at: datetime,
    now: datetime,
    payment_state: str | None = None,
    refund_state: str | None = None,
) -> str:
    if payment_state == "completed":
        if refund_state == "refunded":
            return "refunded"
        if refund_state == "refund_pending":
            return "refund_pending"
        if refund_state == "needs_review":
            return "refund_review"
        return "paid"
    if payment_state == "needs_review":
        return "payment_review"
    if payment_state == "capture_pending":
        return "capture_pending"
    return "expired" if status == "pending_payment" and expires_at <= now else status
