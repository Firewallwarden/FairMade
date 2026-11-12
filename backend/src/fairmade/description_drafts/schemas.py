from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, computed_field, field_validator, model_validator

from fairmade.description_drafts.domain import preview_digest
from fairmade.pricing.schemas import Contract
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse

DescriptionText = Annotated[str, Field(min_length=1, max_length=2000)]


class GenerateDescription(Contract):
    request_id: UUID
    tone: Literal["plain", "friendly"] = "plain"


class ModelDescription(Contract):
    description: DescriptionText


class EditDescription(ModelDescription):
    expected_revision: Revision


class ApproveDescription(Contract):
    expected_revision: Revision
    preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    approved: StrictBool

    @model_validator(mode="after")
    def explicit_review(self) -> Self:
        if not self.approved:
            raise ValueError("Explicit seller review is required")
        return self


class DescriptionDraftResponse(UTCResponse):
    id: UUID
    product_id: UUID
    request_id: UUID
    revision: int
    state: Literal["draft", "approved"]
    generated_text: str
    description: str
    source_snapshot: dict
    source_hash: str
    provider: Literal["ollama_local"]
    model: Literal["qwen3:8b"]
    tone: Literal["plain", "friendly"]
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None

    @field_validator("approved_at")
    @classmethod
    def utc_approval(cls, value):
        return cls.utc_timestamp(value) if value is not None else None

    notices: list[str] = [
        "AI-generated copy, not verified product evidence. Review all factual and quality claims.",
        "Approval applies this text privately; public disclosures need separate approval.",
    ]

    @computed_field
    @property
    def preview_hash(self) -> str:
        return preview_digest(self.id, self.revision, self.description, self.source_hash)
