"""Bounded seller metadata and explicit manual stock events."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.evidence import Amount, today
from fairmade.pricing.schemas import Contract, Label
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse

CanonicalUnit = Literal["g", "ml", "item"]
InputUnit = Literal["g", "kg", "ml", "l", "item"]
MovementKind = Literal["receipt", "usage", "waste", "adjustment"]
Notes = Annotated[str, Field(max_length=2000)]


class MaterialMetadata(Contract):
    name: Label
    notes: Notes | None = None


class MaterialCreate(MaterialMetadata):
    unit: CanonicalUnit


class MaterialReplacement(MaterialMetadata):
    expected_revision: Revision


class MaterialResponse(UTCResponse):
    id: UUID
    name: str
    notes: str | None
    unit: CanonicalUnit
    on_hand: Decimal
    revision: int
    created_at: datetime
    updated_at: datetime
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"


class MovementRequest(Contract):
    expected_revision: Revision
    request_id: UUID
    kind: MovementKind
    quantity: Amount = Field(
        description="Positive change amount; for adjustments, the nonnegative physical count."
    )
    unit: InputUnit
    occurred_on: date
    reason: Annotated[str, Field(min_length=1, max_length=2000)]

    @model_validator(mode="after")
    def meaningful_change(self) -> Self:
        if self.kind != "adjustment" and self.quantity == 0:
            raise ValueError("Receipts, usage and waste require a positive quantity")
        if self.unit == "item" and self.quantity != self.quantity.to_integral_value():
            raise ValueError("Item counts must be whole numbers")
        if self.occurred_on > today():
            raise ValueError("Movement date cannot be in the future")
        if "\x00" in self.reason:
            raise ValueError("Reason cannot contain null characters")
        return self


class MovementResponse(UTCResponse):
    id: UUID
    material_id: UUID
    request_id: UUID
    revision: int
    kind: MovementKind
    material_name: str
    unit: CanonicalUnit
    before: Decimal
    after: Decimal
    delta: Decimal
    request: dict
    created_at: datetime
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
