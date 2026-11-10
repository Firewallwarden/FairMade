"""Private supplier metadata and explicitly reported ratings/delivery observations."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from fairmade.evidence import today
from fairmade.pricing.schemas import Contract, Label
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse

Notes = Annotated[str, Field(max_length=2000)]
Rating = Annotated[int, Field(strict=True, ge=1, le=5)]


class ProfileFields(Contract):
    name: Label
    location: Label | None = None
    notes: Notes | None = None
    archived: StrictBool = False


class ProfileCreate(ProfileFields):
    request_id: UUID


class ProfileReplacement(ProfileFields):
    request_id: UUID
    expected_revision: Revision
    reason: Annotated[str, Field(min_length=1, max_length=2000)]

    @model_validator(mode="after")
    def valid_reason(self) -> Self:
        if "\x00" in self.reason:
            raise ValueError("Reason cannot contain null characters")
        return self


class ProfileResponse(UTCResponse):
    id: UUID
    name: str
    location: str | None
    notes: str | None
    archived: bool
    revision: int
    created_at: datetime
    updated_at: datetime
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"


class ProfileEventResponse(UTCResponse):
    id: UUID
    supplier_id: UUID
    request_id: UUID
    revision: int
    reason: str
    before: dict | None
    after: dict
    created_at: datetime
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"


class ExperienceRequest(Contract):
    request_id: UUID
    expected_supplier_revision: Revision
    label: Label
    observed_on: date
    rating: Rating | None = None
    promised_on: date | None = None
    received_on: date | None = None
    notes: Notes | None = None
    source_quote_id: UUID | None = None
    corrects_experience_id: UUID | None = None
    correction_reason: Annotated[str, Field(min_length=1, max_length=2000)] | None = None

    @model_validator(mode="after")
    def reported_facts(self) -> Self:
        if self.observed_on > today():
            raise ValueError("Observation date cannot be in the future")
        if self.received_on is not None and self.received_on > self.observed_on:
            raise ValueError("Receipt date cannot follow the observation date")
        if (
            self.rating is None
            and self.promised_on is None
            and self.received_on is None
            and not self.notes
        ):
            raise ValueError("Provide a rating, delivery observation or notes")
        if (self.corrects_experience_id is None) != (self.correction_reason is None):
            raise ValueError("A correction requires its prior experience and a reason")
        if self.correction_reason is not None and "\x00" in self.correction_reason:
            raise ValueError("Correction reason cannot contain null characters")
        return self


class ExperienceSummary(UTCResponse):
    id: UUID
    supplier_id: UUID
    request_id: UUID
    supplier_revision: int
    label: str
    observed_on: date
    rating: int | None
    promised_on: date | None
    received_on: date | None
    source_quote_id: UUID | None
    corrects_experience_id: UUID | None
    created_at: datetime
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"


class ExperienceResponse(ExperienceSummary):
    supplier_snapshot: dict
    quote_snapshot: dict | None
    request: dict


class ReliabilityResponse(Contract):
    supplier_id: UUID
    observed_from: date | None
    observed_until: date | None
    experiences_count: int
    rated_count: int
    average_rating: Decimal | None
    dated_deliveries_count: int
    on_time_count: int
    late_count: int
    unknown_delivery_count: int
    on_time_fraction: Decimal | None
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    notices: list[str]
