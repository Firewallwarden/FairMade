"""Review reasons are deliberately shared with applicants; no confidential notes field."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from fairmade.pricing.schemas import Contract
from fairmade.publication import Revision
from fairmade.schemas import SellerApplicationResponse


class DecisionRequest(Contract):
    expected_revision: Revision
    outcome: Literal["approved", "denied"]
    reason: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("reason")
    @classmethod
    def no_null_characters(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Reason cannot contain null characters")
        return value


class AdminApplication(SellerApplicationResponse):
    applicant_account_id: UUID
    applicant_email: str
    decided_by_account_id: UUID | None
