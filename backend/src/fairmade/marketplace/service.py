"""Listing lifecycle: private drafts, exact approval, discovery and deactivation."""

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.marketplace import projection, repository
from fairmade.marketplace.errors import conflict, missing
from fairmade.marketplace.schemas import (
    CatalogCard,
    CatalogDetail,
    ListingContent,
    ListingPreview,
    ReplaceListing,
)
from fairmade.models import MarketplaceListing
from fairmade.passports.repository import visible_publication
from fairmade.passports.schemas import PublicPublication
from fairmade.publication import PublishApproval, public_digest


def get_listing(db: Session, product_id: str) -> MarketplaceListing:
    listing = repository.for_product(db, product_id)
    if listing is None:
        raise missing()
    return listing


def _publication(db: Session, product_id: str, publication_id: str):
    publication = visible_publication(db, publication_id)
    if publication is None or publication.product_id != product_id:
        raise missing()
    return publication


def create(db: Session, product_id: str, content: ListingContent) -> MarketplaceListing:
    _publication(db, product_id, str(content.passport_publication_id))
    if repository.for_product(db, product_id) is not None:
        raise conflict("LISTING_EXISTS", "This product already has a listing.")
    listing = MarketplaceListing(
        product_id=product_id,
        revision=1,
        state="draft",
        content=content.model_dump(mode="json"),
    )
    db.add(listing)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if repository.for_product(db, product_id) is not None:
            raise conflict("LISTING_EXISTS", "This product already has a listing.") from None
        raise
    return listing


def replace(db: Session, product_id: str, body: ReplaceListing) -> MarketplaceListing:
    listing = get_listing(db, product_id)
    content = ListingContent.model_validate(
        body.model_dump(mode="json", exclude={"expected_revision"})
    )
    _publication(db, product_id, str(content.passport_publication_id))
    changed = db.execute(
        update(MarketplaceListing)
        .where(
            MarketplaceListing.id == listing.id,
            MarketplaceListing.revision == body.expected_revision,
        )
        .values(revision=body.expected_revision + 1, content=content.model_dump(mode="json"))
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise conflict()
    db.commit()
    db.expire_all()
    return get_listing(db, product_id)


def preview(db: Session, product_id: str) -> ListingPreview:
    listing = get_listing(db, product_id)
    content = ListingContent.model_validate(listing.content)
    publication = _publication(db, product_id, str(content.passport_publication_id))
    payload = projection.project(content, PublicPublication.model_validate(publication))
    return ListingPreview(
        listing_id=listing.id,
        revision=listing.revision,
        preview_hash=public_digest(payload),
        payload=payload,
    )


def activate(
    db: Session,
    product_id: str,
    body: PublishApproval,
    account_id: str,
) -> MarketplaceListing:
    listing = get_listing(db, product_id)
    if not repository.reserve(db, listing.id, body.expected_revision):
        raise conflict()
    checked = preview(db, product_id)
    if checked.preview_hash != body.preview_hash:
        raise conflict("PREVIEW_MISMATCH", "Approval must match the exact current listing preview.")
    listing = get_listing(db, product_id)
    if listing.state == "active" and listing.published_revision == checked.revision:
        db.commit()
        return listing
    # All searchable fields come from this approved snapshot, never the mutable draft.
    payload = checked.payload
    listing.state = "active"
    listing.published_revision = checked.revision
    listing.published_publication_id = str(payload.passport_id)
    listing.approved_by_account_id = account_id
    listing.published_at = utcnow()
    listing.payload_hash = checked.preview_hash
    listing.public_payload = payload.model_dump(mode="json", exclude_none=True)
    listing.product_type = payload.product.product_type
    listing.search_text = f"{payload.product.title} {payload.seller_display_name}".casefold()
    listing.location_key = payload.location.casefold() if payload.location else None
    # USD amount already validated to whole cents by Passport publication.
    listing.price_minor = int(payload.price.amount * 100)
    db.commit()
    return listing


def deactivate(db: Session, product_id: str) -> None:
    listing = get_listing(db, product_id)
    # Incrementing the revision invalidates any approval prepared before deactivation.
    db.execute(
        update(MarketplaceListing)
        .where(MarketplaceListing.id == listing.id, MarketplaceListing.state != "inactive")
        .values(state="inactive", revision=MarketplaceListing.revision + 1)
        .execution_options(synchronize_session=False)
    )
    db.commit()


def card(listing: MarketplaceListing) -> CatalogCard:
    return CatalogCard(
        id=listing.id,
        published_revision=listing.published_revision,
        published_at=listing.published_at,
        payload_hash=listing.payload_hash,
        payload=listing.public_payload,
    )


def get_public(db: Session, listing_id: str) -> CatalogDetail:
    listing = db.scalar(repository.visible_listings().where(MarketplaceListing.id == listing_id))
    if listing is None:
        raise missing()
    publication = _publication(db, listing.product_id, listing.published_publication_id)
    return CatalogDetail(
        **card(listing).model_dump(),
        passport=PublicPublication.model_validate(publication),
    )
