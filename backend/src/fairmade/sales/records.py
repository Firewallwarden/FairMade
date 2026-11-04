"""Small reporting inputs independent of ORM entities and provider payloads."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SaleRecord:
    order_id: str
    created_at: datetime
    captured_at: datetime
    gross_minor: int
    fee_minor: int | None
    net_minor: int | None
    refund_state: str | None
    refund_minor: int | None
    refund_verified_at: datetime | None
    cost_status: str | None
    cost_total: str | None
    cost_details: dict | None = None
