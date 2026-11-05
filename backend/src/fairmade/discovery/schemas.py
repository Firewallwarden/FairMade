"""Read-only search bodies keep transient buyer coordinates out of URLs."""

from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import Field

from fairmade.geography import ApproximateArea, SearchOrigin
from fairmade.marketplace.schemas import CatalogCard
from fairmade.pricing.schemas import Contract, Label
from fairmade.schemas import ProductType
from fairmade.storefronts.schemas import PublicStorefront


class AreaSearch(Contract):
    origin: SearchOrigin
    radius_km: Annotated[Decimal, Field(ge=1, le=500, decimal_places=1, allow_inf_nan=False)]
    q: Label | None = None
    limit: Annotated[int, Field(strict=True, ge=1, le=100)] = 20
    offset: Annotated[int, Field(strict=True, ge=0, le=9_223_372_036_854_775_807)] = 0


class ListingSearch(AreaSearch):
    product_type: ProductType | None = None


class NearbyStorefront(Contract):
    storefront: PublicStorefront
    estimated_distance_km: str


class NearbyListing(Contract):
    listing: CatalogCard
    storefront_id: UUID
    approximate_area: ApproximateArea
    estimated_distance_km: str


T = TypeVar("T")


class DiscoveryPage(Contract, Generic[T]):
    items: list[T]
    limit: int
    offset: int
    distance_basis: Literal["approximate_area_great_circle"] = "approximate_area_great_circle"
    notices: list[str]
