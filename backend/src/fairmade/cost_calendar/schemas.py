from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from fairmade.money_changes import AmountChange
from fairmade.pricing.schemas import Contract


class CalendarOptions(Contract):
    months: Annotated[int, Field(strict=True, ge=1, le=36)] = 24


class CostMonth(Contract):
    month: str
    status: Literal["recorded", "missing", "basis_changed", "unsupported_snapshot"]
    record_count: int
    compatible_record_count: int
    latest_analysis_id: UUID | None
    latest_saved_on: date | None
    unit_cost: Decimal | None


class AnnualComparison(Contract):
    previous_month: str
    current_month: str
    previous_analysis_id: UUID | None
    current_analysis_id: UUID | None
    status: Literal["comparable", "missing_or_incompatible"]
    difference: AmountChange


class CalendarMonthSummary(Contract):
    calendar_month: int
    observed_years: list[int]
    minimum_unit_cost: Decimal | None
    maximum_unit_cost: Decimal | None


class CostCalendar(Contract):
    calendar_version: Literal["saved-cost-calendar-v1"] = "saved-cost-calendar-v1"
    basis: Literal["seller_recorded_save_month_not_actual_expenses"] = (
        "seller_recorded_save_month_not_actual_expenses"
    )
    product_id: UUID
    product_created_on: date
    as_of_date: date
    start_date: date
    end_date: date
    currency: Literal["USD"] = "USD"
    selling_unit: str
    requested_months: int
    recorded_months: int
    total_snapshots: int
    calendar_evidence_status: Literal["insufficient_history", "descriptive_comparisons_available"]
    seasonality_status: Literal["not_established"] = "not_established"
    months: list[CostMonth]
    year_over_year: list[AnnualComparison]
    calendar_month_summaries: list[CalendarMonthSummary]
    notices: list[str]
