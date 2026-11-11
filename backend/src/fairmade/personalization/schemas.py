from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, field_validator, model_validator

from fairmade.evidence import Amount
from fairmade.marketplace.schemas import CatalogDetail
from fairmade.pricing.schemas import Contract
from fairmade.schemas import ProductType

Revision = Annotated[int, Field(strict=True, ge=0, le=2147483646)]


class Preferences(Contract):
    budget_per_item: Amount | None = None
    product_types: Annotated[list[ProductType], Field(max_length=3)] = Field(default_factory=list)
    location: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    excluded_listing_ids: Annotated[list[UUID], Field(max_length=20)] = Field(default_factory=list)

    @field_validator("product_types", "excluded_listing_ids")
    @classmethod
    def unique_values(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Select each value only once")
        return values


class UpdateProfile(Contract):
    expected_revision: Revision
    enabled: StrictBool
    confirmed: StrictBool
    preferences: Preferences = Field(default_factory=Preferences)

    @model_validator(mode="after")
    def explicit_choice(self) -> Self:
        if not self.confirmed:
            raise ValueError("Explicit confirmation is required")
        if not self.enabled and self.preferences != Preferences():
            raise ValueError("Disabled profiles cannot retain preferences")
        return self


class ProfileResponse(Contract):
    revision: int
    enabled: bool
    preferences: Preferences
    expires_at: datetime | None
    status: Literal["enabled", "disabled", "expired"]
    notices: list[str] = [
        "Opt-in signals use your favorites and recent verified sandbox purchases.",
        "Preferences are not certifications; activity does not establish quality or fairness.",
    ]


class DeleteProfile(Contract):
    expected_revision: Revision


class Suggest(Contract):
    budget_per_item: Amount | None = None
    product_types: Annotated[list[ProductType], Field(max_length=3)] | None = None
    location: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    include_unknown_availability: StrictBool = False

    @field_validator("product_types")
    @classmethod
    def unique_types(cls, values):
        if values is not None and len(values) != len(set(values)):
            raise ValueError("Select each product type once")
        return values


class Suggestion(Contract):
    listing: CatalogDetail
    reasons: list[str]


class Suggestions(Contract):
    items: list[Suggestion]
    personalized: bool
    profile_revision: int
    effective_preferences: Preferences
    notices: list[str]


class MemoryRequest(Contract):
    conversation_id: UUID
    turn_id: UUID


class MemoryExtraction(Contract):
    budget_per_item: Amount | None
    product_types: Annotated[list[ProductType], Field(max_length=3)]


class MemoryProposal(Contract):
    profile_revision: int
    preferences: Preferences
    source_turn_id: UUID
    notices: list[str] = [
        "Proposed from your saved buyer question; review and confirm through the profile API.",
        "No preferences were saved or consent enabled by this proposal.",
    ]
