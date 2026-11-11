"""Bounded buyer activity signals; no provider payloads, prices or private seller data."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.marketplace.repository import visible_listings
from fairmade.models import (
    Favorite,
    MarketplaceListing,
    Order,
    OrderLine,
    PayPalCheckout,
    RefundRequest,
)


def signals(db: Session, account_id: str, listing_ids: list[str]) -> dict:
    if not listing_ids:
        return {"favorites": set(), "purchases": set(), "types": {}}
    public_ids = visible_listings().with_only_columns(MarketplaceListing.id)
    now = utcnow()
    favorite_ids = set(
        db.scalars(
            select(Favorite.listing_id)
            .where(
                Favorite.account_id == account_id,
                Favorite.listing_id.in_(listing_ids),
                Favorite.listing_id.in_(public_ids),
            )
            .limit(201)
        ).all()
    )
    rows = db.execute(
        select(OrderLine.listing_id, MarketplaceListing.product_type)
        .join(Order, Order.id == OrderLine.order_id)
        .join(PayPalCheckout, PayPalCheckout.order_id == Order.id)
        .join(MarketplaceListing, MarketplaceListing.id == OrderLine.listing_id)
        .where(
            Order.buyer_account_id == account_id,
            Order.seller_account_id != account_id,
            PayPalCheckout.state == "completed",
            PayPalCheckout.capture_id.is_not(None),
            PayPalCheckout.verified_at >= now - timedelta(days=90),
            PayPalCheckout.verified_at <= now,
            Order.id.not_in(select(RefundRequest.order_id)),
            MarketplaceListing.id.in_(public_ids),
        )
        .order_by(PayPalCheckout.verified_at.desc(), OrderLine.id)
        .limit(201)
    ).all()
    if len(rows) > 200 or len(favorite_ids) > 200:
        raise api_error(
            409, "PERSONALIZATION_SCOPE_TOO_LARGE", "Activity exceeds the local report limit."
        )
    types: dict[str, int] = {}
    for _listing_id, product_type in rows:
        types[product_type] = min(3, types.get(product_type, 0) + 1)
    return {"favorites": favorite_ids, "purchases": {row[0] for row in rows}, "types": types}
