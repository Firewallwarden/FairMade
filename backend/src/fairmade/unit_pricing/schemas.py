"""A quantity describes one sold unit; it never changes cart or inventory counts."""

from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, model_validator

from fairmade.evidence import PositiveAmount
from fairmade.pricing.schemas import Contract
from fairmade.units import UNITS

SellingUnit = Literal["g", "kg", "ml", "l", "egg", "dozen", "loaf", "item"]
ReferenceUnit = Literal["kg", "l", "egg", "loaf", "item"]


def bounded_decimal_text(value: object) -> object:
    if isinstance(value, str) and len(value) > 64:
        raise ValueError("Quantity decimal text must be at most 64 characters")
    return value


QuantityAmount = Annotated[
    PositiveAmount,
    BeforeValidator(
        bounded_decimal_text, json_schema_input_type=Annotated[str, Field(max_length=64)]
    ),
]


class SellingQuantity(Contract):
    value: QuantityAmount
    unit: SellingUnit

    @model_validator(mode="after")
    def whole_counts(self) -> Self:
        family, factor = UNITS[self.unit]
        if family not in ("mass", "volume"):
            with localcontext() as context:
                context.prec = 60
                count = self.value * factor
                if count != count.to_integral_value():
                    raise ValueError("Count quantities must represent whole eggs, loaves or items")
        return self


class StandardUnitPrice(Contract):
    calculation_version: Literal["standard-unit-pricing-v1"] = "standard-unit-pricing-v1"
    currency: Literal["USD"] = "USD"
    status: Literal["calculated", "below_display_precision"]
    amount: Decimal | None
    reference_unit: ReferenceUnit
    reference_quantity: Literal["1"] = "1"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
