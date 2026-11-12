"""Bounded observation windows and explicit unknown forecast outputs."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from fairmade.pricing.schemas import Contract


class ForecastRequest(Contract):
    lookback_days: Annotated[int, Field(strict=True, ge=14, le=90)] = 28
    horizon_days: Annotated[int, Field(strict=True, ge=1, le=30)] = 7


class DailySales(Contract):
    date: date
    units: int


class History(Contract):
    start_date: date
    end_date: date
    complete_days: int
    sale_dates: int
    included_lines: int
    units: int
    excluded_refund_lines: int
    excluded_basis_lines: int
    excluded_timing_lines: int
    days: list[DailySales]


class InventoryProjection(Contract):
    status: Literal["known", "unknown"]
    available_units: int | None
    projected_remaining_units: Decimal | None
    additional_whole_units: int | None
    days_of_cover: Decimal | None


class ForecastResponse(Contract):
    forecast_version: Literal["observed-sales-rate-v1"] = "observed-sales-rate-v1"
    environment: Literal["sandbox"] = "sandbox"
    basis: Literal["backend_verified_fairmade_captures"] = "backend_verified_fairmade_captures"
    product_id: UUID
    product_type: str
    selling_unit: str
    as_of_date: date
    request: ForecastRequest
    status: Literal["baseline_available", "insufficient_history"]
    history: History
    daily_rate: Decimal | None
    projected_units: Decimal | None
    inventory: InventoryProjection
    warnings: list[str]
    notices: list[str]
