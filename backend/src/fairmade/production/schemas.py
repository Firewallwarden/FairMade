"""Manual completed batches/periods; reported costs are not verified expenses."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.evidence import Amount, today
from fairmade.livestock.schemas import LivestockReference
from fairmade.pricing.schemas import BatchCost, Contract, CostCategory, Label, Labor
from fairmade.schemas import UTCResponse

OutputCount = Annotated[int, Field(strict=True, ge=0, le=1_000_000)]


class RecordedCost(BatchCost):
    amount: Amount


class RecordedLabor(Labor):
    hours: Amount
    hourly_rate: Amount


class ProductionRequest(Contract):
    request_id: UUID
    label: Label
    kind: Literal["batch", "production_period"]
    started_on: date
    completed_on: date
    selling_unit: Label
    total_units: OutputCount
    sellable_units: OutputCount
    currency: Literal["USD"]
    costs: Annotated[list[RecordedCost], Field(max_length=200)]
    labor: Annotated[list[RecordedLabor], Field(max_length=100)]
    notes: Annotated[str, Field(max_length=2000)] | None = None
    corrects_record_id: UUID | None = None
    correction_reason: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    livestock_source: LivestockReference | None = None

    @model_validator(mode="after")
    def completed_and_consistent(self) -> Self:
        if self.started_on > self.completed_on or self.completed_on > today():
            raise ValueError("Production dates must be ordered and not in the future")
        if self.sellable_units > self.total_units:
            raise ValueError("Sellable output cannot exceed total output")
        if (self.corrects_record_id is None) != (self.correction_reason is None):
            raise ValueError("A correction requires both its prior record and a reason")
        if self.correction_reason is not None and "\x00" in self.correction_reason:
            raise ValueError("Correction reason cannot contain null characters")
        return self


class ProductionResult(Contract):
    calculation_version: Literal["completed-production-costs-v1"] = "completed-production-costs-v1"
    currency: Literal["USD"] = "USD"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    category_totals: dict[CostCategory, Decimal]
    labor_total: Decimal
    batch_total: Decimal
    unit_cost: Decimal | None
    unsellable_units: int
    yield_fraction: Decimal | None
    warnings: list[str]


class ProductionSummary(UTCResponse):
    id: UUID
    product_id: UUID
    request_id: UUID
    label: str
    kind: Literal["batch", "production_period"]
    started_on: date
    completed_on: date
    selling_unit: str
    total_units: int
    sellable_units: int
    corrects_record_id: UUID | None
    created_at: datetime
    status: Literal["completed"] = "completed"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"


class ProductionResponse(ProductionSummary):
    product_snapshot: dict
    request: dict
    result: dict
    livestock_snapshot: dict | None = None
