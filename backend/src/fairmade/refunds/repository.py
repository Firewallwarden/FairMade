"""Scoped queries, short order locks and durable refund-operation leases."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.leases import LeaseBusy, claim_lease
from fairmade.models import Order, RefundRequest
from fairmade.refunds.errors import RefundError


def for_order(db: Session, order_id: str) -> RefundRequest | None:
    return db.scalar(select(RefundRequest).where(RefundRequest.order_id == order_id))


def owned_orders(account_id: str, *, seller=False):
    owner = Order.seller_account_id if seller else Order.buyer_account_id
    return select(Order).where(owner == account_id)


def request_page(db: Session, account_id: str, limit: int, offset: int, *, seller=False):
    owner = Order.seller_account_id if seller else Order.buyer_account_id
    return db.scalars(
        select(RefundRequest)
        .join(Order, Order.id == RefundRequest.order_id)
        .where(owner == account_id)
        .order_by(RefundRequest.created_at.desc(), RefundRequest.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()


def lock_order(db: Session, order_id: str) -> Order:
    db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=Order.status)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()
    return db.get(Order, order_id)


def claim(request: RefundRequest) -> str:
    try:
        return claim_lease(request, utcnow())
    except LeaseBusy:
        raise RefundError(
            "REFUND_OPERATION_IN_PROGRESS", "Another refund operation is in progress."
        ) from None
