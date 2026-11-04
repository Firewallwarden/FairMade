"""Shared seller-reported evidence inputs; references are stored, never fetched."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field

from fairmade.database import utcnow
from fairmade.pricing.schemas import Contract, Label


def today() -> date:
    return utcnow().date()


def require_decimal_string(value: object) -> object:
    if not isinstance(value, str):
        raise ValueError("Prices and quantities must be decimal JSON strings")
    return value


Amount = Annotated[
    Decimal,
    BeforeValidator(require_decimal_string, json_schema_input_type=str),
    Field(ge=0, le=1_000_000_000, decimal_places=6, allow_inf_nan=False),
]
PositiveAmount = Annotated[Amount, Field(gt=0)]


class Source(Contract):
    name: Label
    kind: Literal["website", "in_person", "document", "other"]
    reference: Annotated[str, Field(min_length=1, max_length=2000)]
