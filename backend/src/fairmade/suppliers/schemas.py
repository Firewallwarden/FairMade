"""Bounded supplier quotes and explicit, input-specific quality requirements."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.evidence import Amount, PositiveAmount, Source, today
from fairmade.pricing.schemas import Contract, Count, Label
from fairmade.quality.schemas import AttributeKey, Claim, EvaluationResult, Revision, Rule
from fairmade.schemas import UTCResponse

Money = Annotated[Amount, Field(decimal_places=2)]
Fraction = Annotated[PositiveAmount, Field(le=1)]
SupplierUnit = Literal["g", "kg", "ml", "l", "item"]


class SupplyQuantity(Contract):
    value: PositiveAmount
    unit: SupplierUnit

    @model_validator(mode="after")
    def whole_items(self) -> Self:
        if self.unit == "item" and self.value != self.value.to_integral_value():
            raise ValueError("Item quantities must be whole numbers")
        return self


class SourcingInputCreate(Contract):
    label: Label


class SourcingInputResponse(UTCResponse):
    id: UUID
    product_id: UUID
    label: str
    rule_revision: int
    rules: list[Rule]
    created_at: datetime
    updated_at: datetime


class SupplierQuoteData(Contract):
    supplier_name: Label
    source: Source
    location: Label
    observed_on: date
    valid_until: date | None = None
    currency: Literal["USD"]
    package_price: Money
    package_quantity: SupplyQuantity
    usable_fraction: Fraction
    minimum_packages: Count = 1
    maximum_packages: Count | None = None
    # An explicit zero means free/allocated transport; null means unknown.
    transport_cost: Money | None
    availability: Literal["available", "unavailable", "unknown"]
    claims: Annotated[dict[AttributeKey, Claim], Field(max_length=100)]
    notes: Annotated[str, Field(max_length=2000)] | None = None

    @model_validator(mode="after")
    def consistent_quote(self) -> Self:
        if self.valid_until is not None and self.valid_until < self.observed_on:
            raise ValueError("Quote expiry cannot precede the observation date")
        if self.maximum_packages is not None and self.maximum_packages < self.minimum_packages:
            raise ValueError("Maximum packages must be at least the minimum")
        return self

    @model_validator(mode="before")
    @classmethod
    def unambiguous_claims(cls, data: object) -> object:
        if isinstance(data, dict) and isinstance(data.get("claims"), dict):
            keys = [key.strip() if isinstance(key, str) else key for key in data["claims"]]
            if len(keys) != len(set(keys)):
                raise ValueError("Claim keys must be unique after trimming")
        return data


class SupplierQuoteCreate(SupplierQuoteData):
    @model_validator(mode="after")
    def no_future_quote(self) -> Self:
        if self.observed_on > today():
            raise ValueError("Observation date cannot be in the future")
        return self


class SupplierQuoteResponse(UTCResponse):
    id: UUID
    sourcing_input_id: UUID
    created_at: datetime
    basis: Literal["seller_reported_unverified"]
    details: dict


class SupplierQuoteSnapshot(Contract):
    id: UUID
    details: SupplierQuoteData


class SupplierComparisonRequest(Contract):
    quote_ids: Annotated[list[UUID], Field(min_length=1, max_length=100)]
    expected_rule_revision: Revision
    required_quantity: SupplyQuantity
    max_age_days: Annotated[int, Field(strict=True, ge=0, le=365)] = 30

    @model_validator(mode="after")
    def unique_quotes(self) -> Self:
        if len(self.quote_ids) != len(set(self.quote_ids)):
            raise ValueError("Quote IDs must be unique")
        return self


class SupplierCost(Contract):
    packages_to_buy: int
    merchandise_cost: Decimal
    transport_cost: Decimal
    purchase_cost: Decimal
    usable_quantity: Decimal
    surplus_quantity: Decimal
    cost_per_usable_unit: Decimal


class SupplierComparisonRow(Contract):
    quote_id: UUID
    details: SupplierQuoteData
    age_days: int
    quality: EvaluationResult
    cost: SupplierCost | None
    eligible_for_cost_comparison: bool
    exclusion_reasons: list[str]


class SupplierComparisonResult(Contract):
    currency: Literal["USD"] = "USD"
    as_of_date: date
    required_quantity: SupplyQuantity
    rule_revision: int
    quality_evaluation_version: str
    rows: list[SupplierComparisonRow]
    eligible_count: int
    lowest_purchase_cost: Decimal | None
    lowest_cost_per_usable_unit: Decimal | None
    warnings: list[str]


class SupplierReportSummary(UTCResponse):
    id: UUID
    created_at: datetime
    as_of_date: date
    rule_revision: int
    comparison_version: str


class SupplierReportResponse(SupplierReportSummary):
    sourcing_input_id: UUID
    basis: Literal["seller_reported_unverified"]
    request_snapshot: dict
    sourcing_input_snapshot: dict
    product_snapshot: dict
    result: dict
