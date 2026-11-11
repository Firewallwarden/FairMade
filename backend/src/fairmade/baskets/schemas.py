"""Bounded basket needs; quantities and acceptable alternatives belong to the buyer."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from fairmade.evidence import Amount
from fairmade.orders.schemas import CartPreview, CartRequest
from fairmade.passports.schemas import PublicPrice
from fairmade.pricing.schemas import Contract
from fairmade.publication import Revision


class Alternative(Contract):
    listing_id: UUID
    expected_listing_revision: Revision


class Need(Contract):
    group_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")]
    quantity: Annotated[int, Field(strict=True, ge=1, le=10_000)]
    alternatives: Annotated[list[Alternative], Field(min_length=1, max_length=4)]


class BasketRequest(Contract):
    storefront_id: UUID
    budget: Annotated[Amount, Field(decimal_places=2)] | None = None
    needs: Annotated[list[Need], Field(min_length=1, max_length=4)]

    @field_validator("budget", mode="before")
    @classmethod
    def bounded_budget_text(cls, value):
        if isinstance(value, str) and len(value) > 64:
            raise ValueError("Budget text must be at most 64 characters")
        return value

    @model_validator(mode="after")
    def independent_needs(self) -> Self:
        groups = [need.group_id for need in self.needs]
        ids = [item.listing_id for need in self.needs for item in need.alternatives]
        if len(groups) != len(set(groups)):
            raise ValueError("Use a unique group_id for each need")
        if len(ids) != len(set(ids)):
            raise ValueError("Each listing may occur in only one need, once")
        return self


class CandidateDecision(Contract):
    listing_id: UUID
    eligible: bool
    exclusions: list[str]
    affinity_reasons: list[str]


class NeedDecision(Contract):
    group_id: str
    quantity: int
    chosen_listing_id: UUID | None
    candidates: list[CandidateDecision]


class BasketResponse(Contract):
    optimization_version: Literal["single-storefront-basket-v1"] = "single-storefront-basket-v1"
    storefront_id: UUID
    status: Literal["ready", "over_budget", "unavailable"]
    budget: PublicPrice | None
    minimum_subtotal: PublicPrice | None
    remaining_budget: PublicPrice | None
    personalized: bool
    profile_revision: int
    needs: list[NeedDecision]
    cart: CartRequest | None
    preview: CartPreview | None
    notices: list[str]
