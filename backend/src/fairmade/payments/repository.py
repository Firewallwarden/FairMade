"""Short serialized database phases separated from external network requests."""

from datetime import UTC, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import Order, OrderLine, PayPalCheckout, new_id
from fairmade.payments.errors import PaymentError


def lock_order(db: Session, order_id: str) -> Order:
    # Even a no-op UPDATE starts a SQLite write transaction, serializing transitions.
    db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=Order.status)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()
    return db.get(Order, order_id)


def checkout(db: Session, order_id: str) -> PayPalCheckout | None:
    return db.get(PayPalCheckout, order_id)


def claim(payment: PayPalCheckout) -> str:
    now = utcnow()
    deadline = payment.lease_expires_at
    if deadline is not None:
        deadline = deadline.replace(tzinfo=UTC) if deadline.tzinfo is None else deadline
        if deadline > now:
            raise PaymentError(
                "PAYPAL_OPERATION_IN_PROGRESS", "Another payment operation is in progress."
            )
    payment.lease_token = new_id()
    payment.lease_expires_at = now + timedelta(seconds=60)
    return payment.lease_token


def release(payment: PayPalCheckout) -> None:
    payment.lease_token = None
    payment.lease_expires_at = None


def lines(db: Session, order_id: str) -> list[OrderLine]:
    return list(db.scalars(select(OrderLine).where(OrderLine.order_id == order_id)))
