"""Verified order-line sources, author-scoped mutations and visible product projections."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from fairmade.marketplace.repository import visible_listings
from fairmade.models import MarketplaceListing, Order, OrderLine, PayPalCheckout, ProductReview
from fairmade.orders.repository import lock_order


def purchase(db: Session, account_id: str, order_id: str, listing_id: str):
    return db.execute(
        select(OrderLine, PayPalCheckout)
        .join(Order, Order.id == OrderLine.order_id)
        .outerjoin(PayPalCheckout, PayPalCheckout.order_id == Order.id)
        .where(
            Order.id == order_id,
            Order.buyer_account_id == account_id,
            Order.seller_account_id != account_id,
            OrderLine.listing_id == listing_id,
        )
    ).one_or_none()


def reserve_purchase(db: Session, account_id: str, order_id: str) -> None:
    lock_order(db, order_id, account_id, seller=False)


def for_buyer_product(db: Session, buyer_id: str, product_id: str) -> ProductReview | None:
    return db.scalar(
        select(ProductReview).where(
            ProductReview.buyer_account_id == buyer_id, ProductReview.product_id == product_id
        )
    )


def own(db: Session, buyer_id: str, review_id: str) -> ProductReview | None:
    return db.scalar(
        select(ProductReview).where(
            ProductReview.id == review_id, ProductReview.buyer_account_id == buyer_id
        )
    )


def reserve_review(db: Session, buyer_id: str, review_id: str) -> None:
    db.execute(
        update(ProductReview)
        .where(ProductReview.id == review_id, ProductReview.buyer_account_id == buyer_id)
        .values(revision=ProductReview.revision, updated_at=ProductReview.updated_at)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()


def own_page(db: Session, buyer_id: str, limit: int, offset: int) -> list[ProductReview]:
    return list(
        db.scalars(
            select(ProductReview)
            .where(ProductReview.buyer_account_id == buyer_id)
            .order_by(ProductReview.created_at.desc(), ProductReview.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def visible_listing(db: Session, listing_id: str) -> MarketplaceListing | None:
    return db.scalar(visible_listings().where(MarketplaceListing.id == listing_id))


def public_query(listing_id: str):
    # Recheck catalog visibility inside the data query, not just the initial lookup.
    products = (
        visible_listings()
        .where(MarketplaceListing.id == listing_id)
        .with_only_columns(MarketplaceListing.product_id)
    )
    return select(ProductReview).where(
        ProductReview.product_id.in_(products), ProductReview.state == "published"
    )


def public_page(db: Session, listing_id: str, limit: int, offset: int) -> list[ProductReview]:
    return list(
        db.scalars(
            public_query(listing_id)
            .order_by(ProductReview.created_at.desc(), ProductReview.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def totals(db: Session, listing_id: str):
    return db.execute(
        public_query(listing_id).with_only_columns(
            func.count(ProductReview.id), func.coalesce(func.sum(ProductReview.rating), 0)
        )
    ).one()
