"""Append-only, bounded communication; no model, payment or notification dependency."""

from datetime import timedelta

from sqlalchemy.orm import Session

from fairmade.auth import api_error, require_live_session
from fairmade.database import utcnow
from fairmade.models import OrderMessage
from fairmade.order_messages import repository
from fairmade.order_messages.schemas import MessagePage, MessageResponse, SendMessage

MAX_MESSAGES = 1000
MAX_PER_MINUTE = 10


def response(row: OrderMessage, account_id: str) -> MessageResponse:
    return MessageResponse(
        id=row.id,
        sequence=row.sequence,
        sender=row.sender_role,
        is_mine=row.sender_account_id == account_id,
        text=row.text,
        created_at=row.created_at,
    )


def send(
    db: Session, account_id: str, token_hash: str, order_id: str, body: SendMessage
) -> tuple[MessageResponse, bool]:
    repository.participant(db, account_id, order_id)
    repository.reserve(db, account_id, order_id)
    require_live_session(db, token_hash, account_id)
    role = repository.participant(db, account_id, order_id)
    existing = repository.by_request(db, account_id, order_id, str(body.request_id))
    if existing is not None:
        if existing.text != body.text:
            raise api_error(
                409, "REQUEST_ID_CONFLICT", "Use a new request_id for a different message."
            )
        result = response(existing, account_id)
        db.commit()
        return result, False
    sequence = repository.last_sequence(db, order_id)
    if sequence >= MAX_MESSAGES:
        raise api_error(409, "ORDER_MESSAGE_LIMIT", "This order's message history is full.")
    now = utcnow()
    if repository.recent_count(db, account_id, now - timedelta(minutes=1)) >= MAX_PER_MINUTE:
        error = api_error(429, "MESSAGE_RATE_LIMIT", "Wait before sending another message.")
        error.headers = {"Retry-After": "60"}
        raise error
    row = OrderMessage(
        order_id=order_id,
        sequence=sequence + 1,
        sender_account_id=account_id,
        sender_role=role,
        request_id=str(body.request_id),
        text=body.text,
        created_at=now,
    )
    db.add(row)
    db.flush()
    result = response(row, account_id)
    db.commit()
    return result, True


def history(
    db: Session, account_id: str, token_hash: str, order_id: str, after: int, limit: int
) -> MessagePage:
    role = repository.participant(db, account_id, order_id)
    rows = repository.page(db, order_id, after, limit)
    selected = rows[:limit]
    db.expire_all()
    require_live_session(db, token_hash, account_id)
    role = repository.participant(db, account_id, order_id)
    return MessagePage(
        order_id=order_id,
        my_role=role,
        items=[response(row, account_id) for row in selected],
        after_sequence=after,
        next_after_sequence=selected[-1].sequence if selected else after,
        limit=limit,
        has_more=len(rows) > limit,
    )
