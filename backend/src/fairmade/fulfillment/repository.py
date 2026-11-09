"""Owner-filtered orders, serialized writes and bounded append-only event queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.models import Order, PickupFulfillmentEvent
from fairmade.orders import repository as orders


def owned_order(db: Session, account_id: str, order_id: str, *, seller: bool) -> Order | None:
    return db.scalar(orders.owned(db, account_id, seller=seller).where(Order.id == order_id))


def lock_order(db: Session, account_id: str, order_id: str) -> None:
    orders.lock_order(db, order_id, account_id, seller=True)


def latest(db: Session, order_id: str) -> PickupFulfillmentEvent | None:
    return db.scalar(
        select(PickupFulfillmentEvent)
        .where(PickupFulfillmentEvent.order_id == order_id)
        .order_by(PickupFulfillmentEvent.revision.desc())
        .limit(1)
    )


def history(db: Session, order_id: str, limit: int, offset: int) -> list[PickupFulfillmentEvent]:
    return list(
        db.scalars(
            select(PickupFulfillmentEvent)
            .where(PickupFulfillmentEvent.order_id == order_id)
            .order_by(PickupFulfillmentEvent.revision.desc())
            .limit(limit)
            .offset(offset)
        )
    )
