"""Minimal observed sales inputs, independent of storage and provider schemas."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SaleObservation:
    captured_at: datetime
    ordered_at: datetime
    quantity: int
    product_type: str | None
    selling_unit: str | None
    has_refund_request: bool
