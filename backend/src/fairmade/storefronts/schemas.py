"""Public fields are explicit; accounts, credentials and private economics stay private."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fairmade.pricing.schemas import Contract, Label
from fairmade.publication import Revision
from fairmade.schemas import Description, UTCResponse


class StorefrontContent(Contract):
    display_name: Label
    description: Description | None = None
    location: Label | None = None


class ReplaceStorefront(StorefrontContent):
    expected_revision: Revision


class StorefrontDraft(UTCResponse):
    id: UUID
    revision: int
    state: Literal["draft", "published", "withdrawn"]
    created_at: datetime
    updated_at: datetime
    content: StorefrontContent
    published_revision: int | None


class PublicStorefrontContent(Contract):
    storefront_version: Literal["seller-storefront-v1"] = "seller-storefront-v1"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    display_name: str
    description: str | None = None
    location: str | None = None
    notices: list[str]


class StorefrontPreview(Contract):
    storefront_id: UUID
    revision: int
    preview_hash: str
    payload: PublicStorefrontContent


class PublicStorefront(UTCResponse):
    id: UUID
    published_revision: int
    published_at: datetime
    payload_hash: str
    payload: PublicStorefrontContent
