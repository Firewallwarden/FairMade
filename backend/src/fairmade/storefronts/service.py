"""Draft, exact approval and withdrawal; current listings stay independently approved."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.models import Storefront
from fairmade.publication import PublishApproval, public_digest
from fairmade.storefronts import projection, repository
from fairmade.storefronts.schemas import (
    PublicStorefront,
    ReplaceStorefront,
    StorefrontContent,
    StorefrontPreview,
)


def public_response(profile: Storefront) -> PublicStorefront:
    return PublicStorefront(
        id=profile.id,
        published_revision=profile.published_revision,
        published_at=profile.published_at,
        payload_hash=profile.payload_hash,
        payload=profile.public_payload,
    )


def preview(profile: Storefront) -> StorefrontPreview:
    payload = projection.project(StorefrontContent.model_validate(profile.content))
    return StorefrontPreview(
        storefront_id=profile.id,
        revision=profile.revision,
        preview_hash=public_digest(payload),
        payload=payload,
    )


def replace(
    db: Session,
    account_id: str,
    storefront_id: UUID,
    body: ReplaceStorefront,
) -> Storefront:
    profile = repository.owned(db, account_id, storefront_id)
    repository.reserve(db, profile, body.expected_revision)
    profile = repository.owned(db, account_id, storefront_id)
    profile.content = StorefrontContent.model_validate(
        body.model_dump(mode="json", exclude={"expected_revision"})
    ).model_dump(mode="json")
    profile.revision += 1
    db.commit()
    return profile


def publish(
    db: Session,
    account_id: str,
    storefront_id: UUID,
    body: PublishApproval,
) -> PublicStorefront:
    profile = repository.owned(db, account_id, storefront_id)
    repository.reserve(db, profile, body.expected_revision)
    profile = repository.owned(db, account_id, storefront_id)
    checked = preview(profile)
    if checked.preview_hash != body.preview_hash:
        raise api_error(
            409, "PREVIEW_MISMATCH", "Approval must match the exact current storefront preview."
        )
    if profile.state == "published" and profile.published_revision == checked.revision:
        db.commit()
        return public_response(profile)
    payload = checked.payload
    profile.state = "published"
    profile.published_revision = checked.revision
    profile.published_at = utcnow()
    profile.payload_hash = checked.preview_hash
    profile.public_payload = payload.model_dump(mode="json", exclude_none=True)
    profile.search_text = f"{payload.display_name} {payload.description or ''}".casefold()
    profile.location_key = payload.location.casefold() if payload.location else None
    db.commit()
    return public_response(profile)


def withdraw(db: Session, account_id: str, storefront_id: UUID) -> None:
    profile = repository.owned(db, account_id, storefront_id)
    # Revision increments invalidate all approvals prepared before withdrawal.
    db.execute(
        update(Storefront)
        .where(Storefront.id == profile.id, Storefront.state != "withdrawn")
        .values(state="withdrawn", revision=Storefront.revision + 1)
        .execution_options(synchronize_session=False)
    )
    db.commit()
