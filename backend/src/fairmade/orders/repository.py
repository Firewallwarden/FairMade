"""Order lookup and ownership filters; no HTTP dependencies."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from fairmade.models import Order


def by_key(db: Session, buyer_id: str, key: str) -> Order | None:
    return db.scalar(
        select(Order).where(Order.buyer_account_id == buyer_id, Order.idempotency_key == key)
    )


def owned(db: Session, account_id: str, *, seller: bool = False):
    owner = Order.seller_account_id if seller else Order.buyer_account_id
    return (
        select(Order)
        .options(
            joinedload(Order.checkout),
            joinedload(Order.refund_request),
        )
        .where(owner == account_id)
    )


def lock_order(db: Session, order_id: str, account_id: str, *, seller: bool) -> None:
    owner = Order.seller_account_id if seller else Order.buyer_account_id
    db.execute(
        update(Order)
        .where(Order.id == order_id, owner == account_id)
        .values(status=Order.status)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()
