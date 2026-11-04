"""Explicit USD prices, quantities, provenance, and comparison selection."""

from datetime import date, datetime
from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.comparisons.units import UNITS, named_unit_matches
from fairmade.evidence import Amount as Amount
from fairmade.evidence import PositiveAmount as PositiveAmount
from fairmade.evidence import Source as Source
from fairmade.evidence import today as today
from fairmade.pricing.schemas import Contract, Label
from fairmade.schemas import ProductType, UTCResponse

Unit = Literal["g", "kg", "egg", "dozen", "loaf", "item"]
Notes = Annotated[str, Field(max_length=2000)]


class Quantity(Contract):
    value: PositiveAmount
    unit: Unit

    @model_validator(mode="after")
    def whole_count(self) -> Self:
        family, factor = UNITS[self.unit]
        if family != "mass":
            with localcontext() as context:
                context.prec = 60
                count = self.value * factor
                if count != count.to_integral_value():
                    raise ValueError("Count quantities must represent whole eggs, loaves, or items")
        return self


class ObservationData(Contract):
    label: Label
    product_type: ProductType
    currency: Literal["USD"]
    price: Amount
    quantity: Quantity
    source: Source
    location: Label
    observed_on: date
    quality_notes: Notes | None = None
    price_notes: Notes | None = None

    @model_validator(mode="after")
    def meaningful_named_units(self) -> Self:
        if not named_unit_matches(self.product_type, self.quantity.unit):
            raise ValueError("Named egg/dozen/loaf units must match the declared product type")
        return self


class ObservationCreate(ObservationData):
    @model_validator(mode="after")
    def no_future_observations(self) -> Self:
        if self.observed_on > today():
            raise ValueError("Observation date cannot be in the future")
        return self


class ObservationResponse(UTCResponse):
    id: UUID
    product_id: UUID
    created_at: datetime
    basis: Literal["seller_reported_unverified"]
    # Stored input is returned unchanged; reading is independent of future validators.
    details: dict


class ObservationSnapshot(Contract):
    id: UUID
    details: ObservationData


class ComparisonRequest(Contract):
    observation_ids: Annotated[list[UUID], Field(min_length=1, max_length=100)]
    target_quantity: Quantity
    max_age_days: Annotated[int, Field(strict=True, ge=0, le=365)] = 30

    @model_validator(mode="after")
    def distinct_observations(self) -> Self:
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("Observation IDs must be unique")
        return self


class ComparisonRow(Contract):
    observation_id: UUID
    details: ObservationData
    age_days: int
    stale: bool
    included_in_range: bool
    normalized_price: Decimal | None
    exclusion_reasons: list[str]


class SelectedPriceRange(Contract):
    included_count: int
    excluded_count: int
    minimum: Decimal | None
    maximum: Decimal | None


class ComparisonResult(Contract):
    currency: Literal["USD"] = "USD"
    target_quantity: Quantity
    max_age_days: int
    as_of_date: date
    rows: list[ComparisonRow]
    selected_price_range: SelectedPriceRange
    warnings: list[str]


class ReportSummary(UTCResponse):
    id: UUID
    created_at: datetime
    as_of_date: date
    comparison_version: str


class ReportResponse(ReportSummary):
    product_id: UUID
    basis: Literal["seller_reported_unverified"]
    request_snapshot: dict
    product_snapshot: dict
    result: dict
