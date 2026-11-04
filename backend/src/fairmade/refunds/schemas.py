"""Participant-private request/decision records and sanitized refund receipts."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from fairmade.passports.schemas import PublicPrice
from fairmade.pricing.schemas import Contract
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse

Reason = Annotated[str, Field(min_length=1, max_length=1000)]


class CreateRequest(Contract):
    reason: Reason


class ApproveRequest(Contract):
    expected_revision: Revision


class DenyRequest(ApproveRequest):
    reason: Reason


class EmptyRequest(Contract):
    pass


class RefundResponse(UTCResponse):
    id: UUID
    order_id: UUID
    revision: int
    state: Literal["requested", "denied", "refund_pending", "refunded", "failed", "needs_review"]
    reason: str
    created_at: datetime
    decision: Literal["approved", "denied"] | None
    decision_reason: str | None
    decision_expected_revision: int | None
    decided_at: datetime | None
    amount: PublicPrice
    environment: Literal["sandbox"] = "sandbox"
    merchant_mode: Literal["shared"] = "shared"
    provider_refund_id: str | None
    provider_status: str | None
    verified_at: datetime | None

    @field_validator("decided_at", "verified_at")
    @classmethod
    def utc_optional(cls, value):
        return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value
