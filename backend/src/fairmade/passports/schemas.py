"""Explicit disclosure policy and allowlisted public output types."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, StrictBool, model_validator

from fairmade.comparisons.schemas import Amount, Quantity
from fairmade.composition.schemas import CompositionDisclosure
from fairmade.pricing.schemas import Contract, CostCategory, Label
from fairmade.publication import PublishApproval as PublishApproval
from fairmade.publication import Revision as Revision
from fairmade.quality.schemas import Rule
from fairmade.schemas import ProductType, UTCResponse

SellerPrice = Annotated[Amount, Field(gt=0, decimal_places=2)]
PublicDescription = Annotated[str, Field(max_length=2000)]


class DisclosurePolicy(Contract):
    cost_categories: Annotated[list[CostCategory], Field(max_length=8)] = Field(
        default_factory=list
    )
    include_labor: StrictBool = False
    include_unit_cost: StrictBool = False
    include_quality_requirements: StrictBool = False
    include_quality_summary: StrictBool = False
    include_market_context: StrictBool = False
    include_composition: StrictBool = False

    @model_validator(mode="after")
    def unique_categories(self) -> Self:
        if len(set(self.cost_categories)) != len(self.cost_categories):
            raise ValueError("Cost category disclosures must be unique")
        return self


class DraftContent(Contract):
    # Preserve the existing OpenAPI component name when nested quantity schemas differ by mode.
    model_config = ConfigDict(json_schema_mode_override="validation")

    review_id: UUID
    title: Label
    price: SellerPrice
    public_description: PublicDescription | None = None
    disclosures: DisclosurePolicy = Field(default_factory=DisclosurePolicy)
    composition: CompositionDisclosure | None = None

    @model_validator(mode="after")
    def composition_disclosure_needs_data(self) -> Self:
        if self.disclosures.include_composition and self.composition is None:
            raise ValueError("Provide composition before enabling its disclosure")
        return self


class ReplaceDraft(DraftContent):
    expected_revision: Revision


class DraftResponse(UTCResponse):
    id: UUID
    product_id: UUID
    revision: int
    created_at: datetime
    updated_at: datetime
    content: DraftContent


class PublicProduct(Contract):
    title: str
    product_type: ProductType
    selling_unit: str
    description: str | None = None


class PublicPrice(Contract):
    currency: Literal["USD"] = "USD"
    amount: Decimal


class DisclosedCosts(Contract):
    category_costs_per_unit: dict[CostCategory, Decimal] = Field(default_factory=dict)
    labor_per_unit: Decimal | None = None
    unit_cost: Decimal | None = None


class PublicQualitySummary(Contract):
    status: Literal["not_provided", "needs_attention", "claims_match_unverified"]
    evaluation_count: int
    failed_count: int
    unknown_or_unevaluated_count: int
    outdated_count: int


class PublicMarketContext(Contract):
    status: Literal[
        "not_provided",
        "product_type_mismatch",
        "basis_missing",
        "no_comparable_evidence",
        "comparable",
    ]
    quantity: Quantity | None = None
    included_count: int
    minimum: Decimal | None = None
    maximum: Decimal | None = None


class PublicPassport(Contract):
    passport_version: Literal["fair-price-passport-v1"] = "fair-price-passport-v1"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    reviewed_on: date
    product: PublicProduct
    price: PublicPrice
    costs: DisclosedCosts | None = None
    quality_requirements: list[Rule] | None = None
    quality_summary: PublicQualitySummary | None = None
    market_context: PublicMarketContext | None = None
    composition: CompositionDisclosure | None = None
    notices: list[str]


class Preview(Contract):
    draft_id: UUID
    revision: int
    preview_hash: str
    payload: PublicPassport


class PublicationResponse(UTCResponse):
    id: UUID
    draft_revision: int
    state: Literal["published", "withdrawn", "superseded"]
    created_at: datetime
    withdrawn_at: datetime | None
    payload_hash: str
    payload: PublicPassport

    @model_validator(mode="after")
    def utc_withdrawal(self) -> Self:
        if self.withdrawn_at is not None and self.withdrawn_at.tzinfo is None:
            self.withdrawn_at = self.withdrawn_at.replace(tzinfo=UTC)
        return self


class PublicPublication(UTCResponse):
    id: UUID
    created_at: datetime
    payload_hash: str
    payload: PublicPassport
