"""Explicit publication consent and privacy-preserving review projections."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, field_validator, model_validator

from fairmade.pricing.schemas import Contract
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse


class ReviewContent(Contract):
    rating: Annotated[int, Field(strict=True, ge=1, le=5)]
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    publish: StrictBool

    @field_validator("text")
    @classmethod
    def reject_null_characters(cls, value: str) -> str:
        # SQLite text length semantics stop at NUL; reject it before persistence.
        if "\x00" in value:
            raise ValueError("Review text cannot contain null characters")
        return value

    @model_validator(mode="after")
    def explicit_consent(self) -> Self:
        if not self.publish:
            raise ValueError("Publication requires explicit consent")
        return self


class ReviewUpdate(ReviewContent):
    expected_revision: Revision


class WithdrawReview(Contract):
    expected_revision: Revision


class PublicReview(UTCResponse):
    id: UUID
    rating: int
    text: str
    created_at: datetime
    updated_at: datetime
    reviewer_label: Literal["Verified sandbox buyer"] = "Verified sandbox buyer"
    purchase_basis: Literal["sandbox_capture_verified_at_submission"] = (
        "sandbox_capture_verified_at_submission"
    )
    claims_basis: Literal["buyer_reported_unverified"] = "buyer_reported_unverified"


class OwnReview(UTCResponse):
    id: UUID
    order_id: UUID
    listing_id: UUID
    revision: int
    state: Literal["published", "withdrawn"]
    rating: int
    text: str
    created_at: datetime
    updated_at: datetime


class RatingSummary(Contract):
    review_count: int
    average_rating: str | None
    notices: list[str]
