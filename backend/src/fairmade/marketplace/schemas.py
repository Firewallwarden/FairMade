"""Private listing drafts and explicit allowlisted public catalog schemas."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from fairmade.availability.schemas import ListingAvailability
from fairmade.passports.schemas import PublicPrice, PublicProduct, PublicPublication
from fairmade.photos.schemas import PhotoSelection, PublicPhoto
from fairmade.pricing.schemas import Contract, Label
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse


class ListingContent(Contract):
    passport_publication_id: UUID
    seller_display_name: Label
    location: Label | None = None
    summary: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    photos: Annotated[list[PhotoSelection], Field(max_length=6)] | None = None

    @field_validator("photos")
    @classmethod
    def unique_photos(cls, value):
        if value is not None and len({photo.photo_id for photo in value}) != len(value):
            raise ValueError("Select each photo only once")
        return value


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
    photos: list[PublicPhoto] | None = None


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
    availability: ListingAvailability


class CatalogDetail(CatalogCard):
    passport: PublicPublication
