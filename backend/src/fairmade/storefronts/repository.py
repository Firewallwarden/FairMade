"""Owner-scoped drafts and current published visibility; one storefront per MVP seller."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.availability.query import with_availability
from fairmade.availability.schemas import AvailabilityStatus
from fairmade.database import utcnow
from fairmade.geography import ApproximateArea
from fairmade.marketplace.repository import visible_listings
from fairmade.models import (
    AccountRole,
    MarketplaceListing,
    Product,
    Storefront,
    StorefrontDiscoveryLocation,
    new_id,
)
from fairmade.storefronts.schemas import StorefrontContent


def owned(db: Session, account_id: str, storefront_id: UUID) -> Storefront:
    profile = db.scalar(
        select(Storefront).where(
            Storefront.id == str(storefront_id),
            Storefront.account_id == account_id,
        )
    )
    if profile is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return profile


def create(db: Session, account_id: str, content: StorefrontContent) -> Storefront:
    profile_id = new_id()
    now = utcnow()
    created = db.execute(
        insert(Storefront)
        .values(
            id=profile_id,
            account_id=account_id,
            revision=1,
            state="draft",
            content=content.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["account_id"])
    )
    if created.rowcount != 1:
        raise api_error(
            409, "STOREFRONT_LIMIT", "The local MVP supports one storefront per seller account."
        )
    db.commit()
    return db.get(Storefront, profile_id)


def own_page(db: Session, account_id: str, limit: int, offset: int) -> list[Storefront]:
    return list(
        db.scalars(
            select(Storefront)
            .where(Storefront.account_id == account_id)
            .order_by(Storefront.created_at.desc(), Storefront.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def reserve(db: Session, profile: Storefront, revision: int) -> None:
    changed = db.execute(
        update(Storefront)
        .where(Storefront.id == profile.id, Storefront.revision == revision)
        .values(revision=revision, updated_at=Storefront.updated_at)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise api_error(
            409, "REVISION_CONFLICT", "The storefront revision changed; reload and retry."
        )
    db.expire_all()


def visible():
    return (
        select(Storefront)
        .join(AccountRole, AccountRole.account_id == Storefront.account_id)
        .where(Storefront.state == "published", AccountRole.role == "seller")
    )


def save_approved_area(db: Session, storefront_id: str, area: ApproximateArea | None) -> None:
    """Commit the search index together with the exact approved public payload."""
    if area is None:
        row = db.get(StorefrontDiscoveryLocation, storefront_id)
        if row is not None:
            db.delete(row)
        return
    values = {
        "latitude_hundredths": int(area.latitude * 100),
        "longitude_hundredths": int(area.longitude * 100),
    }
    db.execute(
        insert(StorefrontDiscoveryLocation)
        .values(storefront_id=storefront_id, **values)
        .on_conflict_do_update(index_elements=["storefront_id"], set_=values)
    )


def public_profile(db: Session, storefront_id: UUID) -> Storefront:
    profile = db.scalar(visible().where(Storefront.id == str(storefront_id)))
    if profile is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return profile


def browse(
    db: Session,
    query: str | None,
    location: str | None,
    limit: int,
    offset: int,
) -> list[Storefront]:
    statement = visible()
    if query:
        statement = statement.where(
            Storefront.search_text.contains(query.casefold(), autoescape=True)
        )
    if location:
        statement = statement.where(Storefront.location_key == location.casefold())
    return list(
        db.scalars(
            statement.order_by(Storefront.published_at.desc(), Storefront.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def listings(
    db: Session,
    storefront_id: UUID,
    limit: int,
    offset: int,
    availability: AvailabilityStatus | None = None,
):
    # Recheck storefront visibility in the listing query itself as well. A
    # concurrent withdrawal must not expose unpublished/private product data.
    accounts = (
        visible()
        .where(Storefront.id == str(storefront_id))
        .with_only_columns(Storefront.account_id)
    )
    products = select(Product.id).where(Product.account_id.in_(accounts))
    # Product ownership is the MVP assignment rule; the storefront UUID remains
    # independent so explicit per-store assignments can be added later.
    statement = (
        with_availability(visible_listings(), availability)
        .where(MarketplaceListing.product_id.in_(products))
        .order_by(MarketplaceListing.published_at.desc(), MarketplaceListing.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(statement))
