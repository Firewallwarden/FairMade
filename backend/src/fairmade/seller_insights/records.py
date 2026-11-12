"""Storage-independent saved-cost comparison inputs."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CostObservation:
    identifier: str
    created_on: date
    product_type: str | None
    selling_unit: str | None
    unit_cost: Decimal | None
