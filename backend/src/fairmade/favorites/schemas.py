"""Bookmarks preserve public listing IDs, never stale catalog or private product data."""

from datetime import datetime
from uuid import UUID

from fairmade.marketplace.schemas import CatalogCard
from fairmade.pricing.schemas import Contract
from fairmade.schemas import UTCResponse


class FavoriteCreate(Contract):
    listing_id: UUID


class FavoriteResponse(UTCResponse):
    id: UUID
    listing_id: UUID
    created_at: datetime
    listing_visible: bool
    listing: CatalogCard | None
