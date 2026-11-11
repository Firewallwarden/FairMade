"""Small immutable source values shared by persistence and calendar arithmetic."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Snapshot:
    identifier: str
    saved_on: date
    product_type: str | None
    selling_unit: str | None
    unit_cost: Decimal | None
