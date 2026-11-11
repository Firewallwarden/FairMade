from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BeforeValidator,
    Field,
    StrictBool,
    computed_field,
    field_validator,
    model_validator,
)

from fairmade.evidence import require_decimal_string
from fairmade.pricing.schemas import Contract
from fairmade.receipts.domain import preview_digest, review_issues
from fairmade.schemas import UTCResponse

Money = Annotated[
    Decimal,
    BeforeValidator(require_decimal_string, json_schema_input_type=str),
    Field(ge=0, le=1_000_000_000, decimal_places=2, allow_inf_nan=False),
]
Revision = Annotated[int, Field(strict=True, ge=1, le=2147483646)]


class LineItem(Contract):
    description: Annotated[str, Field(min_length=1, max_length=200)]
    line_total: Money | None


class ExtractedReceipt(Contract):
    merchant: Annotated[str, Field(min_length=1, max_length=200)] | None
    date_text: Annotated[str, Field(min_length=1, max_length=40)] | None
    currency: Literal["USD"] | None
    subtotal: Money | None
    tax: Money | None
    total: Money | None
    items: Annotated[list[LineItem], Field(max_length=50)]


class ExpenseDetails(Contract):
    merchant: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    purchased_on: date | None = None
    currency: Literal["USD"] | None = None
    subtotal: Money | None = None
    tax: Money | None = None
    total: Money | None = None
    items: Annotated[list[LineItem], Field(max_length=50)] = []
    category: Literal[
        "materials", "packaging", "transport", "utilities", "equipment", "overhead", "other"
    ] = "other"


class ImportReceipt(Contract):
    request_id: UUID
    image_base64: Annotated[str, Field(min_length=1, max_length=6990508)]


class EditReceipt(Contract):
    expected_revision: Revision
    details: ExpenseDetails


class ApproveReceipt(Contract):
    expected_revision: Revision
    preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    approved: StrictBool

    @model_validator(mode="after")
    def explicit_approval(self) -> Self:
        if not self.approved:
            raise ValueError("Explicit seller review is required")
        return self


class ReceiptResponse(UTCResponse):
    id: UUID
    request_id: UUID
    source_hash: str
    revision: int
    state: Literal["draft", "approved"]
    ocr_text: str
    provenance: dict[str, str]
    extracted: ExtractedReceipt
    details: ExpenseDetails
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None

    @field_validator("approved_at")
    @classmethod
    def utc_approval(cls, value):
        return cls.utc_timestamp(value) if value is not None else None

    @computed_field
    @property
    def preview_hash(self) -> str:
        return preview_digest(self.id, self.revision, self.details.model_dump(mode="json"))

    @computed_field
    @property
    def approval_blockers(self) -> list[str]:
        return review_issues(self.details.model_dump(mode="json"))

    notices: list[str] = [
        "Local OCR/AI draft; extracted fields are unverified and require seller review.",
        "No inventory, recipe, production cost, public disclosure or payment is changed.",
        "Payment-line redaction is best effort. Do not upload sensitive or unrelated documents.",
    ]


class ExpenseResponse(UTCResponse):
    id: UUID
    receipt_id: UUID
    details: ExpenseDetails
    created_at: datetime
    basis: Literal["seller_reviewed_unverified"] = "seller_reviewed_unverified"
