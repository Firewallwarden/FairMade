"""Versioned pricing contract. Rates are fractions, not percentages."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Amount = Annotated[Decimal, Field(ge=0, le=1_000_000_000, decimal_places=6, allow_inf_nan=False)]
Rate = Annotated[Decimal, Field(ge=0, lt=1, decimal_places=6, allow_inf_nan=False)]
Label = Annotated[str, Field(min_length=1, max_length=200)]
Count = Annotated[int, Field(strict=True, gt=0, le=1_000_000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CostCategory(StrEnum):
    MATERIALS = "materials"
    PACKAGING = "packaging"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    EQUIPMENT = "equipment"
    OVERHEAD = "overhead"
    RISK_RESERVE = "risk_reserve"
    OTHER = "other"


class BatchCost(Contract):
    label: Label
    category: CostCategory
    amount: Amount = Field(description="Total cost allocated to this entire batch, in USD.")


class Labor(Contract):
    label: Label
    hours: Amount
    hourly_rate: Amount


class PaymentFees(Contract):
    rate: Rate = Field(description="Seller-supplied processing rate; 0.03 means 3%.")
    fixed_per_order: Amount
    units_per_order: Count = Field(description="Expected sellable units sharing one fixed fee.")


class MarginTargets(Contract):
    minimum: Rate
    maximum: Rate

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.maximum < self.minimum:
            raise ValueError("maximum margin must be at least minimum margin")
        return self


class PricingRequest(Contract):
    currency: Literal["USD"]
    sellable_units: Count = Field(description="Actual usable batch yield after waste.")
    costs: Annotated[list[BatchCost], Field(max_length=200)]
    labor: Annotated[list[Labor], Field(max_length=100)]
    payment_fees: PaymentFees
    target_margin: MarginTargets
    proposed_prices: Annotated[list[Amount], Field(max_length=50)] = Field(default_factory=list)

    @model_validator(mode="after")
    def feasible(self) -> Self:
        if self.payment_fees.rate + self.target_margin.maximum >= 1:
            raise ValueError("processing rate plus maximum target margin must be less than 1")
        return self


class CostBreakdown(Contract):
    category_totals: dict[CostCategory, Decimal]
    labor_total: Decimal
    batch_total: Decimal
    unit_cost: Decimal


class PriceRange(Contract):
    minimum: Decimal
    maximum: Decimal


class PriceScenario(Contract):
    price: Decimal
    processing_fee_per_unit: Decimal
    profit_per_unit: Decimal
    batch_profit: Decimal
    margin: Decimal | None
    markup: Decimal | None
    below_break_even: bool
    below_target_margin: bool


class Warning(Contract):
    code: str
    message: str


class PricingResponse(Contract):
    calculation_version: Literal["production-economics-v1"] = "production-economics-v1"
    currency: Literal["USD"] = "USD"
    basis: Literal["seller_supplied_unverified"] = "seller_supplied_unverified"
    costs: CostBreakdown
    fixed_fee_per_unit: Decimal
    break_even_price: Decimal
    sustainable_price_range: PriceRange
    scenarios: list[PriceScenario]
    warnings: list[Warning]
    assumptions: list[str]
