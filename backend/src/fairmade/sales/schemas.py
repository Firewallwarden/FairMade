"""Seller-only reporting DTOs; never added to buyer orders or public listings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import field_validator

from fairmade.pricing.schemas import Contract
from fairmade.quality.schemas import Revision
from fairmade.schemas import UTCResponse


class SelectCostBasis(Contract):
    expected_revision: Revision
    analysis_id: UUID | None


class CostBasisResponse(Contract):
    product_id: UUID
    revision: int
    analysis_id: UUID | None
    source_snapshot: dict | None


class SalesOrderResponse(UTCResponse):
    environment: Literal["sandbox"] = "sandbox"
    merchant_mode: Literal["shared"] = "shared"
    order_id: UUID
    created_at: datetime
    captured_at: datetime
    currency: Literal["USD"] = "USD"
    gross_sales: Decimal
    completed_refunds: Decimal
    processing_fee: Decimal | None
    fee_basis: Literal["provider_fee", "derived_from_provider_net", "unavailable"]
    after_refunds_and_fee: Decimal | None
    estimated_production_cost: Decimal | None
    estimated_profit: Decimal | None
    estimated_margin: Decimal | None
    profit_unavailable_reasons: list[str]
    cost_snapshot: dict | None
    warnings: list[str]

    # UTCResponse handles created_at; capture verification uses the same UTC storage.
    @field_validator("captured_at")
    @classmethod
    def capture_time(cls, value: datetime) -> datetime:
        return cls.utc_timestamp(value)


class SalesSummary(Contract):
    report_version: Literal["sandbox-sales-v1"] = "sandbox-sales-v1"
    environment: Literal["sandbox"] = "sandbox"
    merchant_mode: Literal["shared"] = "shared"
    period_basis: Literal["capture_verified_at"] = "capture_verified_at"
    refund_basis: Literal["completed_refunds_as_of_report"] = "completed_refunds_as_of_report"
    currency: Literal["USD"] = "USD"
    start_date: date
    end_date: date
    generated_at: datetime
    sales_count: int
    gross_sales: Decimal
    completed_refunds: Decimal
    sales_less_refunds: Decimal
    known_processing_fees: Decimal
    known_estimated_production_costs: Decimal
    missing_fee_count: int
    missing_cost_count: int
    unresolved_refund_count: int
    covered_sales_count: int
    covered_estimated_profit: Decimal
    estimated_profit: Decimal | None
    estimated_margin: Decimal | None
    warnings: list[str]
