"""Database operations for Passport drafts and versioned publication."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import (
    AccountRole,
    PassportDraft,
    PassportPublication,
    Product,
    SellerPricingReview,
)


def review_for_product(db: Session, product_id: str, review_id: str):
    return db.scalar(
        select(SellerPricingReview).where(
            SellerPricingReview.product_id == product_id,
            SellerPricingReview.id == review_id,
        )
    )


def draft_for_product(db: Session, product_id: str, draft_id: str):
    return db.scalar(
        select(PassportDraft).where(
            PassportDraft.product_id == product_id,
            PassportDraft.id == draft_id,
        )
    )


def reserve_draft(db: Session, product_id: str, draft_id: str, revision: int) -> bool:
    changed = db.execute(
        update(PassportDraft)
        .where(
            PassportDraft.product_id == product_id,
            PassportDraft.id == draft_id,
            PassportDraft.revision == revision,
        )
        .values(
            revision=revision,
            updated_at=PassportDraft.updated_at,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount:
        db.expire_all()
    return changed.rowcount == 1


def publications_for_revision(db: Session, draft_id: str, revision: int):
    return db.scalar(
        select(PassportPublication).where(
            PassportPublication.draft_id == draft_id,
            PassportPublication.draft_revision == revision,
        )
    )


def supersede_product_publications(db: Session, product_id: str) -> None:
    db.execute(
        update(PassportPublication)
        .where(
            PassportPublication.product_id == product_id,
            PassportPublication.state == "published",
        )
        .values(state="superseded", withdrawn_at=utcnow())
        .execution_options(synchronize_session=False)
    )


def publication_for_draft(db: Session, draft_id: str, publication_id: str):
    return db.scalar(
        select(PassportPublication).where(
            PassportPublication.draft_id == draft_id,
            PassportPublication.id == publication_id,
        )
    )


def visible_publications():
    # Public visibility is also revoked when the account loses seller access.
    return (
        select(PassportPublication)
        .join(
            Product,
            Product.id == PassportPublication.product_id,
        )
        .join(AccountRole, AccountRole.account_id == Product.account_id)
        .where(
            PassportPublication.state == "published",
            AccountRole.role == "seller",
        )
    )


def visible_publication(db: Session, publication_id: str):
    return db.scalar(visible_publications().where(PassportPublication.id == publication_id))
