"""Participant authorization and a short serialized append transaction."""

from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.models import AccountRole, Order, OrderMessage
from fairmade.order_messages.schemas import ParticipantRole


def participant(db: Session, account_id: str, order_id: str) -> ParticipantRole:
    order = db.scalar(
        select(Order).where(
            Order.id == order_id,
            or_(Order.buyer_account_id == account_id, Order.seller_account_id == account_id),
        )
    )
    if order is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    if order.buyer_account_id == account_id:
        return "buyer"
    if db.get(AccountRole, (account_id, "seller")) is None:
        raise api_error(403, "SELLER_REQUIRED", "Verified seller access is required.")
    return "seller"


def reserve(db: Session, account_id: str, order_id: str) -> None:
    # SQLite serializes writes before retry, rate and sequence checks. This
    # no-op does not change business order state or reserve any stock.
    result = db.execute(
        update(Order)
        .where(
            Order.id == order_id,
            or_(Order.buyer_account_id == account_id, Order.seller_account_id == account_id),
        )
        .values(status=Order.status)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    db.expire_all()


def by_request(db: Session, account_id: str, order_id: str, request_id: str) -> OrderMessage | None:
    return db.scalar(
        select(OrderMessage).where(
            OrderMessage.order_id == order_id,
            OrderMessage.sender_account_id == account_id,
            OrderMessage.request_id == request_id,
        )
    )


def last_sequence(db: Session, order_id: str) -> int:
    return db.scalar(
        select(func.coalesce(func.max(OrderMessage.sequence), 0)).where(
            OrderMessage.order_id == order_id,
        )
    )


def recent_count(db: Session, account_id: str, since: datetime) -> int:
    return db.scalar(
        select(func.count())
        .select_from(OrderMessage)
        .where(
            OrderMessage.sender_account_id == account_id,
            OrderMessage.created_at > since,
        )
    )


def page(db: Session, order_id: str, after: int, limit: int) -> list[OrderMessage]:
    return list(
        db.scalars(
            select(OrderMessage)
            .where(
                OrderMessage.order_id == order_id,
                OrderMessage.sequence > after,
            )
            .order_by(OrderMessage.sequence)
            .limit(limit + 1)
        )
    )
