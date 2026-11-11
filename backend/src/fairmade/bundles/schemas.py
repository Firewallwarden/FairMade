"""Explicit candidate scope; bundles never introduce a new price or product."""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from fairmade.baskets.schemas import Alternative, CandidateDecision
from fairmade.evidence import Amount
from fairmade.marketplace.schemas import CatalogDetail
from fairmade.orders.schemas import CartRequest
from fairmade.passports.schemas import PublicPrice
from fairmade.pricing.schemas import Contract


class BundleRequest(Contract):
    storefront_id: UUID
    candidates: Annotated[list[Alternative], Field(min_length=2, max_length=8)]
    budget: Annotated[Amount, Field(decimal_places=2)] | None = None
    limit: Annotated[int, Field(strict=True, ge=1, le=4)] = 3

    @field_validator("budget", mode="before")
    @classmethod
    def budget_text(cls, value):
        if isinstance(value, str) and len(value) > 64:
            raise ValueError("Budget text must be at most 64 characters")
        return value

    @model_validator(mode="after")
    def distinct_candidates(self) -> Self:
        ids = [row.listing_id for row in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Select each candidate once")
        return self


class BundleSuggestion(Contract):
    listings: list[CatalogDetail]
    quantity_each: Literal[1] = 1
    subtotal: PublicPrice
    reasons: list[str]
    observed_copurchase_orders: int | None
    cart: CartRequest | None


class BundleReport(Contract):
    bundle_version: Literal["same-storefront-pairs-v1"] = "same-storefront-pairs-v1"
    role: Literal["seller", "buyer"]
    storefront_id: UUID
    budget: PublicPrice | None
    personalized: bool
    profile_revision: int
    candidates: list[CandidateDecision]
    suggestions: list[BundleSuggestion]
    eligible_pairs: int
    budget_excluded_pairs: int
    history_start_date: date | None
    history_end_date: date | None
    notices: list[str]
