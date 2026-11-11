"""Explicit product/seller scopes and typed financial/quantity evidence."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from fairmade.pricing.schemas import Contract
from fairmade.receipts.aggregates import ExpenseTotals


class InsightOptions(Contract):
    period_days: Annotated[int, Field(strict=True, ge=1, le=90)] = 30


class InsightRequest(InsightOptions):
    analysis_id: UUID | None = None


class Window(Contract):
    start_date: date
    end_date: date


class AmountChange(Contract):
    change: Decimal | None
    relative_change: Decimal | None


class ExpenseComparison(Contract):
    previous: ExpenseTotals
    current: ExpenseTotals
    difference: AmountChange


class PriceAssessment(Contract):
    status: Literal["missing_analysis", "missing_listing", "incompatible_basis", "assessed"]
    analysis_id: UUID | None = None
    analysis_saved_on: date | None = None
    listing_id: UUID | None = None
    listing_revision: int | None = None
    price: Decimal | None = None
    unit_cost: Decimal | None = None
    break_even_price: Decimal | None = None
    target_price_minimum: Decimal | None = None
    target_price_maximum: Decimal | None = None
    profit_per_unit: Decimal | None = None
    margin: Decimal | None = None
    below_break_even: bool | None = None
    below_target_margin: bool | None = None


class CostComparison(Contract):
    status: Literal["available", "missing_period_evidence", "incompatible_basis"]
    previous_analysis_id: UUID | None = None
    current_analysis_id: UUID | None = None
    previous_saved_on: date | None = None
    current_saved_on: date | None = None
    previous_unit_cost: Decimal | None = None
    current_unit_cost: Decimal | None = None
    difference: AmountChange


class ProductionOutput(Contract):
    included_records: int
    excluded_basis_records: int
    total_units: int
    sellable_units: int
    non_sellable_units: int
    sellable_fraction: Decimal | None


class MaterialWaste(Contract):
    material_id: UUID
    label: str
    unit: Literal["g", "ml", "item"]
    quantity: Decimal
    movement_count: int


class InsightAlert(Contract):
    code: str
    severity: Literal["warning", "opportunity", "information"]
    scope: Literal["product", "seller"]
    source: Literal["pricing", "cost_history", "receipts", "production", "materials"]
    message: str
    suggested_review: str


class InsightReport(Contract):
    insight_version: Literal["seller-insights-v1"] = "seller-insights-v1"
    product_id: UUID
    selling_unit: str
    as_of_date: date
    currency: Literal["USD"] = "USD"
    current_period: Window
    previous_period: Window
    pricing: PriceAssessment
    costs: CostComparison
    receipts: ExpenseComparison
    production: ProductionOutput
    materials: list[MaterialWaste]
    alerts: list[InsightAlert]
    notices: list[str]
