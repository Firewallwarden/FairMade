"""Scoped writes and visibility queries for approved catalog snapshots."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.availability.query import with_availability
from fairmade.availability.schemas import AvailabilityStatus
from fairmade.models import MarketplaceListing, PassportPublication
from fairmade.passports.repository import visible_publications


def for_product(db: Session, product_id: str):
    return db.scalar(select(MarketplaceListing).where(MarketplaceListing.product_id == product_id))


def reserve(db: Session, listing_id: str, revision: int) -> bool:
    changed = db.execute(
        update(MarketplaceListing)
        .where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.revision == revision,
        )
        .values(revision=revision, updated_at=MarketplaceListing.updated_at)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount:
        db.expire_all()
    return changed.rowcount == 1


def visible_listings():
    visible_ids = visible_publications().with_only_columns(PassportPublication.id)
    return select(MarketplaceListing).where(
        MarketplaceListing.state == "active",
        MarketplaceListing.published_publication_id.in_(visible_ids),
    )


def filtered_listings(*, query: str | None, product_type: str | None, location: str | None):
    statement = visible_listings()
    if query:
        # Treat %, _ and / literally rather than as SQL LIKE patterns.
        statement = statement.where(
            MarketplaceListing.search_text.contains(query.casefold(), autoescape=True)
        )
    if product_type:
        statement = statement.where(MarketplaceListing.product_type == product_type)
    if location:
        statement = statement.where(MarketplaceListing.location_key == location.casefold())
    return statement


def browse(
    db: Session,
    *,
    query: str | None,
    product_type: str | None,
    location: str | None,
    limit: int,
    offset: int,
    availability: AvailabilityStatus | None = None,
):
    statement = with_availability(
        filtered_listings(
            query=query,
            product_type=product_type,
            location=location,
        ),
        availability,
    )
    return db.execute(
        statement.order_by(MarketplaceListing.published_at.desc(), MarketplaceListing.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
