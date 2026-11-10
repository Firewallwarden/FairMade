"""Owner filters and current visibility are evaluated together in bounded SQL queries."""

from uuid import UUID

from sqlalchemy import DateTime, and_, delete, literal, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.availability.query import public_availability, with_availability
from fairmade.database import utcnow
from fairmade.favorites.schemas import FavoriteResponse
from fairmade.marketplace.repository import visible_listings
from fairmade.marketplace.schemas import CatalogCard
from fairmade.models import Favorite, MarketplaceListing, new_id


def _owned(account_id: str):
    visible_ids = visible_listings().with_only_columns(MarketplaceListing.id).correlate(None)
    statement = (
        select(Favorite, MarketplaceListing)
        .select_from(Favorite)
        .outerjoin(
            MarketplaceListing,
            and_(
                MarketplaceListing.id == Favorite.listing_id,
                MarketplaceListing.id.in_(visible_ids),
            ),
        )
        .where(Favorite.account_id == account_id)
    )
    return with_availability(statement)


def _response(row) -> FavoriteResponse:
    favorite = row[0]
    listing = None
    visible = row[1]
    if visible is not None:
        listing = CatalogCard(
            id=visible.id,
            published_revision=visible.published_revision,
            published_at=visible.published_at,
            payload_hash=visible.payload_hash,
            payload=visible.public_payload,
            availability=public_availability(row),
        )
    return FavoriteResponse(
        id=favorite.id,
        listing_id=favorite.listing_id,
        created_at=favorite.created_at,
        listing_visible=listing is not None,
        listing=listing,
    )


def create(db: Session, account_id: str, listing_id: UUID) -> tuple[FavoriteResponse, bool]:
    # INSERT SELECT takes the write transaction before visibility is checked.
    # Seller withdrawal and duplicate submissions cannot race a stale precheck.
    visible = visible_listings().where(MarketplaceListing.id == str(listing_id))
    source = visible.with_only_columns(
        literal(new_id()),
        literal(account_id),
        MarketplaceListing.id,
        literal(utcnow(), type_=DateTime()),
    )
    result = db.execute(
        insert(Favorite)
        .from_select(
            ["id", "account_id", "listing_id", "created_at"],
            source,
            include_defaults=False,
        )
        .on_conflict_do_nothing(index_elements=["account_id", "listing_id"])
    )
    row = db.execute(_owned(account_id).where(Favorite.listing_id == str(listing_id))).first()
    if row is None or row[1] is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    response = _response(row)
    db.commit()
    return response, result.rowcount == 1


def page(db: Session, account_id: str, limit: int, offset: int) -> list[FavoriteResponse]:
    rows = db.execute(
        _owned(account_id)
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_response(row) for row in rows]


def get(db: Session, account_id: str, favorite_id: UUID) -> FavoriteResponse:
    row = db.execute(_owned(account_id).where(Favorite.id == str(favorite_id))).first()
    if row is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return _response(row)


def remove(db: Session, account_id: str, favorite_id: UUID) -> None:
    removed = db.execute(
        delete(Favorite).where(Favorite.id == str(favorite_id), Favorite.account_id == account_id)
    )
    if removed.rowcount != 1:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    db.commit()
