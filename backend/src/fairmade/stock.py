"""Shared sellable-stock queries; reservations are derived from unexpired unpaid orders."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from fairmade.models import MarketplaceListing, Order, OrderLine, SellableInventory


@dataclass(frozen=True)
class StockBalance:
    revision: int
    selling_unit: str | None
    on_hand: int
    reserved: int

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


def lock_products(db: Session, product_ids) -> None:
    # SQLite starts a serialized write transaction even if this matches no rows.
    # Re-read stock/order state after acquiring it; never trust an earlier read.
    db.execute(
        update(SellableInventory)
        .where(SellableInventory.product_id.in_(product_ids))
        .values(revision=SellableInventory.revision)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()


def lock_for_listings(db: Session, listing_ids: list[str]) -> None:
    lock_products(
        db,
        select(MarketplaceListing.product_id).where(MarketplaceListing.id.in_(listing_ids)),
    )


def balance(db: Session, product_id: str, now: datetime) -> StockBalance:
    reserved = (
        select(func.coalesce(func.sum(OrderLine.quantity), 0))
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            OrderLine.product_id == product_id,
            Order.status == "pending_payment",
            Order.expires_at > now,
        )
        .scalar_subquery()
    )
    # One statement prevents a stock read and a reservation read observing
    # different committed states during concurrent requests.
    row = db.execute(
        select(
            SellableInventory.revision,
            SellableInventory.selling_unit,
            SellableInventory.on_hand,
            reserved.label("reserved"),
        ).where(SellableInventory.product_id == product_id)
    ).one_or_none()
    return StockBalance(
        revision=row.revision if row else 0,
        selling_unit=row.selling_unit if row else None,
        on_hand=row.on_hand if row else 0,
        reserved=row.reserved if row else 0,
    )
