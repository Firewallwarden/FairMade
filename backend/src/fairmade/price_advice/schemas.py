"""Read-only conditional advice; no universal fairness or automatic price selection."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fairmade.comparisons.schemas import Quantity
from fairmade.evidence import Source
from fairmade.pricing.schemas import Contract, PriceRange


class AdviceRequest(Contract):
    review_id: UUID


class MarketSource(Contract):
    observation_id: UUID
    label: str
    location: str
    observed_on: date
    source: Source
    included: bool
    normalized_price: Decimal | None
    exclusions: list[str]


class AdviceReport(Contract):
    advice_version: Literal["conditional-price-range-v1"] = "conditional-price-range-v1"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    product_id: UUID
    review_id: UUID
    pricing_analysis_id: UUID
    analysis_saved_on: date
    as_of_date: date
    analysis_selling_unit: str
    current_selling_unit: str
    status: Literal[
        "economics_only",
        "conditional_overlap",
        "quality_blocked",
        "basis_changed",
        "target_market_gap",
        "market_premium_gap",
        "no_cent_price",
    ]
    quality_status: Literal["not_configured", "selected_claims_match_unverified", "blocked"]
    current_rule_revision: int
    market_status: str
    currency: Literal["USD"] = "USD"
    unit_cost: Decimal
    break_even_price: Decimal
    seller_target_range: PriceRange
    selected_market_range: PriceRange | None
    recommended_review_range: PriceRange | None
    production_unit_quantity: Quantity | None
    market_reference_quantity: Quantity | None
    selected_quality_evaluation_ids: list[UUID]
    market_sources: list[MarketSource]
    reasons: list[str]
    notices: list[str]
