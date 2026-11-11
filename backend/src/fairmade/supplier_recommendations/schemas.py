"""Seller-selected priorities never replace mandatory input requirements."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.evidence import Source
from fairmade.pricing.schemas import Contract
from fairmade.quality.schemas import QualityCheck, Rule
from fairmade.suppliers.schemas import SupplierCost, SupplyQuantity


class RecommendationOptions(Contract):
    mode: Literal["savings", "quality", "balanced"] = "balanced"
    cost_objective: Literal["purchase_outlay", "usable_unit"] = "purchase_outlay"
    preferences: Annotated[list[Rule], Field(max_length=8)] = Field(default_factory=list)

    @model_validator(mode="after")
    def distinct_preferences(self) -> Self:
        keys = [rule.key for rule in self.preferences]
        if len(keys) != len(set(keys)):
            raise ValueError("Use each optional preference key once")
        return self


class RecommendationRequest(RecommendationOptions):
    supplier_report_id: UUID


class RecommendationRow(Contract):
    quote_id: UUID
    supplier_name: str
    observed_on: date
    source: Source
    mandatory_checks: list[QualityCheck]
    preference_checks: list[QualityCheck]
    eligible: bool
    exclusion_reasons: list[str]
    cost: SupplierCost | None
    objective_cost: Decimal | None
    preference_matches: list[bool]
    selected_for_input_review: bool
    selection_reason: Literal["excluded", "selected", "not_selected"]


class RecommendationReport(Contract):
    recommendation_version: Literal["supplier-review-modes-v1"] = "supplier-review-modes-v1"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    product_id: UUID
    supplier_report_id: UUID
    sourcing_input_id: UUID
    input_label: str
    rule_revision: int
    as_of_date: date
    required_quantity: SupplyQuantity
    options: RecommendationOptions
    rows: list[RecommendationRow]
    selected_quote_ids: list[UUID]
    product_impact: Literal["not_assessed_no_substitution_authorized"] = (
        "not_assessed_no_substitution_authorized"
    )
    notices: list[str]
