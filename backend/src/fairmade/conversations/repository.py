"""Bounded queries and compare-and-swap writes; never hold a lock during inference."""

from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.models import Account, AssistantConversation, AssistantTurn

RETENTION_DAYS = 30
MAX_CONVERSATIONS = 20
MAX_TURNS = 40


def expires_after(now):
    return now + timedelta(days=RETENTION_DAYS)


def owned(db: Session, account_id: str, conversation_id: str) -> AssistantConversation:
    db.expire_all()
    row = db.scalar(
        select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.account_id == account_id,
            AssistantConversation.expires_at > utcnow(),
        )
    )
    if row is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return row


def request_turn(db: Session, conversation_id: str, request_id: str) -> AssistantTurn | None:
    return db.scalar(
        select(AssistantTurn).where(
            AssistantTurn.conversation_id == conversation_id,
            AssistantTurn.request_id == request_id,
        )
    )


def recent(db: Session, conversation_id: str) -> list[AssistantTurn]:
    rows = db.scalars(
        select(AssistantTurn)
        .where(AssistantTurn.conversation_id == conversation_id)
        .order_by(AssistantTurn.revision.desc())
        .limit(6)
    ).all()
    return list(reversed(rows))


def reserve_account(db: Session, account_id: str) -> None:
    db.execute(
        update(Account)
        .where(Account.id == account_id)
        .values(created_at=Account.created_at)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()


def purge_expired(db: Session, account_id: str | None = None) -> int:
    statement = delete(AssistantConversation).where(AssistantConversation.expires_at <= utcnow())
    if account_id is not None:
        statement = statement.where(AssistantConversation.account_id == account_id)
    return db.execute(statement.execution_options(synchronize_session=False)).rowcount


def append_revision(db: Session, account_id: str, conversation_id: str, revision: int) -> bool:
    now = utcnow()
    result = db.execute(
        update(AssistantConversation)
        .where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.account_id == account_id,
            AssistantConversation.revision == revision,
            AssistantConversation.expires_at > now,
        )
        .values(revision=revision + 1, updated_at=now, expires_at=expires_after(now))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1
