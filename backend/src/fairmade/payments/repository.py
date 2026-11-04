"""Short serialized database phases separated from external network requests."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.leases import LeaseBusy, claim_lease, release_lease
from fairmade.models import Order, OrderLine, PayPalCheckout
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
    try:
        return claim_lease(payment, utcnow())
    except LeaseBusy:
        raise PaymentError(
            "PAYPAL_OPERATION_IN_PROGRESS", "Another payment operation is in progress."
        ) from None


def release(payment: PayPalCheckout) -> None:
    release_lease(payment)


def lines(db: Session, order_id: str) -> list[OrderLine]:
    return list(db.scalars(select(OrderLine).where(OrderLine.order_id == order_id)))
