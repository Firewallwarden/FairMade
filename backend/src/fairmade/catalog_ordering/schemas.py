"""Additive page metadata keeps ordering evidence separate from listing disclosures."""

from typing import Literal, Self
from uuid import UUID

from pydantic import model_validator

from fairmade.marketplace.schemas import CatalogCard
from fairmade.pricing.schemas import Contract
from fairmade.schemas import Page, ProductType
from fairmade.unit_pricing.schemas import ReferenceUnit

SortMode = Literal["newest", "price_asc", "price_desc", "quality", "unit_price", "value"]
QualityStatus = Literal["undisclosed", "not_provided", "needs_attention", "claims_match_unverified"]


class OrderingOptions(Contract):
    mode: SortMode
    product_type: ProductType | None = None
    reference_unit: ReferenceUnit | None = None

    @model_validator(mode="after")
    def compatible_scope(self) -> Self:
        if self.mode in ("unit_price", "value"):
            if self.product_type is None or self.reference_unit is None:
                raise ValueError(
                    "Unit-price/value ordering requires product_type and reference_unit"
                )
        elif self.reference_unit is not None:
            raise ValueError("reference_unit applies only to unit_price/value ordering")
        return self


class OrderingSignal(Contract):
    listing_id: UUID
    quality_status: QualityStatus
    quality_basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    comparison_status: Literal["ordered", "not_compared"]
    reasons: list[str]


class OrderingMetadata(Contract):
    policy_version: Literal["catalog-ordering-v1"] = "catalog-ordering-v1"
    mode: SortMode
    product_type: ProductType | None
    reference_unit: ReferenceUnit | None
    candidate_count: int
    compared_count: int
    not_compared_count: int
    items: list[OrderingSignal]
    notices: list[str]


class OrderedCatalogPage(Page[CatalogCard]):
    ordering: OrderingMetadata | None = None
