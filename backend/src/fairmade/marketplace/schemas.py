"""Private listing drafts and explicit allowlisted public catalog schemas."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from fairmade.passports.schemas import PublicPrice, PublicProduct, PublicPublication
from fairmade.pricing.schemas import Contract, Label
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse


class ListingContent(Contract):
    passport_publication_id: UUID
    seller_display_name: Label
    location: Label | None = None
    summary: Annotated[str, Field(min_length=1, max_length=1000)] | None = None


class ReplaceListing(ListingContent):
    expected_revision: Revision


class ListingResponse(UTCResponse):
    id: UUID
    product_id: UUID
    revision: int
    state: Literal["draft", "active", "inactive"]
    created_at: datetime
    updated_at: datetime
    published_revision: int | None
    content: ListingContent


class CatalogContent(Contract):
    listing_version: Literal["marketplace-listing-v1"] = "marketplace-listing-v1"
    product: PublicProduct
    price: PublicPrice
    seller_display_name: str
    location: str | None = None
    summary: str | None = None
    passport_id: UUID
    passport_payload_hash: str
    notices: list[str]


class ListingPreview(Contract):
    listing_id: UUID
    revision: int
    preview_hash: str
    payload: CatalogContent


class CatalogCard(UTCResponse):
    id: UUID
    published_revision: int
    published_at: datetime
    payload_hash: str
    payload: CatalogContent


class CatalogDetail(CatalogCard):
    passport: PublicPublication
