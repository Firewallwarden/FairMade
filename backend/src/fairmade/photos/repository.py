"""Local SQLite blob storage; metadata queries never load image bytes implicitly."""

from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, undefer

from fairmade.marketplace.repository import visible_listings
from fairmade.models import ListingPhoto, MarketplaceListing, Product, ProductPhoto
from fairmade.photos.errors import photo_error as api_error
from fairmade.photos.processing import NormalizedPhoto

MAX_PRODUCT_PHOTOS = 10
MAX_ACCOUNT_BYTES = 64 * 1024 * 1024


def reserve_product(db: Session, product_id: str) -> None:
    db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(updated_at=Product.updated_at)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()


def owned(db: Session, product_id: str, photo_id: UUID | str, *, with_bytes=False) -> ProductPhoto:
    statement = select(ProductPhoto).where(
        ProductPhoto.id == str(photo_id),
        ProductPhoto.product_id == product_id,
    )
    if with_bytes:
        statement = statement.options(undefer(ProductPhoto.image_bytes))
    photo = db.scalar(statement)
    if photo is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return photo


def save(db: Session, product_id: str, account_id: str, image: NormalizedPhoto) -> ProductPhoto:
    reserve_product(db, product_id)
    count = db.scalar(
        select(func.count())
        .select_from(ProductPhoto)
        .where(
            ProductPhoto.product_id == product_id,
        )
    )
    account_bytes = db.scalar(
        select(func.coalesce(func.sum(ProductPhoto.byte_count), 0))
        .join(Product, Product.id == ProductPhoto.product_id)
        .where(Product.account_id == account_id)
    )
    if count >= MAX_PRODUCT_PHOTOS or account_bytes + len(image.data) > MAX_ACCOUNT_BYTES:
        raise api_error(409, "PHOTO_STORAGE_LIMIT", "Remove unused photos before uploading more.")
    photo = ProductPhoto(
        product_id=product_id,
        width=image.width,
        height=image.height,
        byte_count=len(image.data),
        sha256=image.sha256,
        image_bytes=image.data,
    )
    db.add(photo)
    db.commit()
    return photo


def page(db: Session, product_id: str, limit: int, offset: int) -> list[ProductPhoto]:
    return list(
        db.scalars(
            select(ProductPhoto)
            .where(ProductPhoto.product_id == product_id)
            .order_by(ProductPhoto.created_at.desc(), ProductPhoto.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def replace_public_links(db: Session, listing_id: str, photo_ids: list[str]) -> None:
    db.execute(delete(ListingPhoto).where(ListingPhoto.listing_id == listing_id))
    db.add_all([ListingPhoto(listing_id=listing_id, photo_id=photo_id) for photo_id in photo_ids])


def public_photo(db: Session, photo_id: UUID) -> ProductPhoto:
    visible_ids = visible_listings().with_only_columns(MarketplaceListing.id)
    photo = db.scalar(
        select(ProductPhoto)
        .options(undefer(ProductPhoto.image_bytes))
        .join(ListingPhoto, ListingPhoto.photo_id == ProductPhoto.id)
        .where(ProductPhoto.id == str(photo_id), ListingPhoto.listing_id.in_(visible_ids))
    )
    if photo is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return photo


def remove(db: Session, product_id: str, photo_id: UUID) -> None:
    reserve_product(db, product_id)
    photo = owned(db, product_id, photo_id)
    listing = db.scalar(
        select(MarketplaceListing).where(MarketplaceListing.product_id == product_id)
    )
    draft_ids = (
        {item["photo_id"] for item in (listing.content.get("photos") or [])} if listing else set()
    )
    active_link = db.scalar(
        select(ListingPhoto.photo_id)
        .join(MarketplaceListing)
        .where(ListingPhoto.photo_id == photo.id, MarketplaceListing.state == "active")
    )
    if photo.id in draft_ids or active_link is not None:
        raise api_error(
            409, "PHOTO_IN_USE", "Remove the photo from the draft and active listing first."
        )
    db.execute(delete(ListingPhoto).where(ListingPhoto.photo_id == photo.id))
    db.delete(photo)
    db.commit()
