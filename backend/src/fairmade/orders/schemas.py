"""Strict cart input and historical, public-data-only order snapshots."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.marketplace.schemas import CatalogContent
from fairmade.passports.schemas import PublicPrice
from fairmade.pricing.schemas import Contract
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse


class CartLine(Contract):
    listing_id: UUID
    expected_listing_revision: Revision
    quantity: Annotated[int, Field(strict=True, ge=1, le=10_000)]


class CartRequest(Contract):
    items: Annotated[list[CartLine], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def unique_listings(self) -> Self:
        ids = [item.listing_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Listing IDs must be unique")
        return self


class PricedLine(Contract):
    listing_id: UUID
    published_revision: int
    quantity: int
    unit_price: PublicPrice
    subtotal: PublicPrice
    listing: CatalogContent


class CartPreview(Contract):
    order_version: Literal["unpaid-order-v1"] = "unpaid-order-v1"
    items: list[PricedLine]
    subtotal: PublicPrice
    notices: list[str]


class OrderResponse(UTCResponse):
    id: UUID
    status: Literal[
        "pending_payment",
        "cancelled",
        "expired",
        "capture_pending",
        "payment_review",
        "paid",
        "refund_pending",
        "refund_review",
        "refunded",
    ]
    created_at: datetime
    expires_at: datetime
    snapshot: CartPreview
