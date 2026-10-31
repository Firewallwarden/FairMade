"""Explicit evidence selection and an optional seller-declared unit mapping."""

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.comparisons.schemas import Quantity
from fairmade.pricing.schemas import Contract
from fairmade.schemas import UTCResponse


class ReviewRequest(Contract):
    pricing_analysis_id: UUID
    comparison_report_id: UUID | None = None
    quality_evaluation_ids: Annotated[list[UUID], Field(max_length=100)] = Field(
        default_factory=list
    )
    production_unit_quantity: Quantity | None = None

    @model_validator(mode="after")
    def coherent_selection(self) -> Self:
        if len(set(self.quality_evaluation_ids)) != len(self.quality_evaluation_ids):
            raise ValueError("Quality evaluation IDs must be unique")
        if self.production_unit_quantity is not None and self.comparison_report_id is None:
            raise ValueError("A production-unit mapping requires a comparison report")
        return self


class ReviewSummary(UTCResponse):
    id: UUID
    created_at: datetime
    reviewed_on: date
    review_version: str


class ReviewResponse(ReviewSummary):
    product_id: UUID
    basis: Literal["seller_reported_unverified"]
    request_snapshot: dict
    evidence_snapshot: dict
    result: dict
