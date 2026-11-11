"""Owner-only profile state with explicit consent, expiry, and revision-safe erasure."""

from datetime import UTC, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.models import Account, BuyerProfile
from fairmade.personalization.erasure import erase_answers
from fairmade.personalization.schemas import Preferences, ProfileResponse, UpdateProfile


def active(row: BuyerProfile | None) -> bool:
    return bool(
        row and row.enabled and row.expires_at and row.expires_at.replace(tzinfo=UTC) > utcnow()
    )


def get(db: Session, account_id: str) -> ProfileResponse:
    row = db.get(BuyerProfile, account_id)
    enabled = active(row)
    return ProfileResponse(
        revision=row.revision if row else 0,
        enabled=enabled,
        preferences=Preferences.model_validate(row.preferences) if enabled else Preferences(),
        expires_at=row.expires_at.replace(tzinfo=UTC) if row and row.expires_at else None,
        status="enabled" if enabled else ("expired" if row and row.enabled else "disabled"),
    )


def reserve(db: Session, account_id: str) -> None:
    db.execute(
        update(Account)
        .where(Account.id == account_id)
        .values(created_at=Account.created_at)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()


def put(db: Session, account_id: str, body: UpdateProfile) -> ProfileResponse:
    reserve(db, account_id)
    row = db.get(BuyerProfile, account_id)
    revision = row.revision if row else 0
    if revision != body.expected_revision:
        raise api_error(409, "REVISION_CONFLICT", "Reload the current buyer profile.")
    if revision >= 2147483646 and body.enabled:
        raise api_error(409, "REVISION_LIMIT", "Profile revision limit reached.")
    if row is None:
        row = BuyerProfile(account_id=account_id)
        db.add(row)
    row.revision = min(2147483646, revision + 1)
    row.enabled = body.enabled
    row.preferences = body.preferences.model_dump(mode="json") if body.enabled else {}
    row.expires_at = utcnow() + timedelta(days=30) if body.enabled else None
    row.updated_at = utcnow()
    if not body.enabled:
        erase_answers(db, account_id)
    db.commit()
    return get(db, account_id)


def erase(db: Session, account_id: str, revision: int) -> ProfileResponse:
    # A minimal revision tombstone prevents a stale tab from restoring deleted preferences.
    return put(
        db,
        account_id,
        UpdateProfile(
            expected_revision=revision, enabled=False, confirmed=True, preferences=Preferences()
        ),
    )
