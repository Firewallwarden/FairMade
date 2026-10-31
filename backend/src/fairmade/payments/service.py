"""Durable payment phases: claim/commit, provider I/O, then verified local settlement."""

from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade import stock
from fairmade.database import utcnow
from fairmade.marketplace.repository import visible_listings
from fairmade.models import MarketplaceListing, Order, PayPalCheckout, SellableInventory
from fairmade.orders import repository as orders
from fairmade.orders.domain import effective_status, money
from fairmade.payments import repository
from fairmade.payments.errors import PaymentError, ProviderError, VerificationError, unavailable
from fairmade.payments.gateway import Gateway
from fairmade.payments.schemas import CheckoutResponse
from fairmade.payments.verification import VerifiedPayment, verify


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def owned_order(db: Session, account_id: str, order_id: str, *, seller=False) -> Order:
    order = db.scalar(orders.owned(db, account_id, seller=seller).where(Order.id == order_id))
    if order is None:
        raise PaymentError("NOT_FOUND", "The requested resource was not found.", 404)
    return order


def get_checkout(db: Session, order_id: str) -> PayPalCheckout:
    payment = repository.checkout(db, order_id)
    if payment is None:
        raise PaymentError("NOT_FOUND", "The requested resource was not found.", 404)
    return payment


def response(payment: PayPalCheckout) -> CheckoutResponse:
    return CheckoutResponse(
        order_id=payment.order_id,
        state=payment.state,
        provider_order_id=payment.provider_order_id,
        provider_status=payment.provider_status,
        capture_id=payment.capture_id,
        amount=money(payment.amount_minor),
        sandbox_fee=money(payment.fee_minor) if payment.fee_minor is not None else None,
        sandbox_net=money(payment.net_minor) if payment.net_minor is not None else None,
        verified_at=_utc(payment.verified_at) if payment.verified_at else None,
    )


def _payable(db: Session, order: Order) -> None:
    if effective_status(order.status, _utc(order.expires_at), utcnow()) != "pending_payment":
        raise PaymentError("ORDER_NOT_PAYABLE", "The order is cancelled, expired or already paid.")
    # Do not initiate a new charge after a seller hides or changes an approved listing.
    for line in order.snapshot["items"]:
        visible = db.scalar(
            visible_listings().where(
                MarketplaceListing.id == line["listing_id"],
                MarketplaceListing.published_revision == line["published_revision"],
            )
        )
        if visible is None:
            raise PaymentError(
                "ORDER_LISTING_CHANGED", "Review the current listing and create a new order."
            )


def _begin(
    db: Session,
    account_id: str,
    order_id: str,
    gateway: Gateway,
    action: str,
    *,
    seller=False,
) -> tuple[PayPalCheckout, str | None, bool]:
    owned_order(db, account_id, order_id, seller=seller)
    order = repository.lock_order(db, order_id)
    payment = repository.checkout(db, order_id)
    if payment and payment.merchant_id != gateway.merchant_id:
        raise PaymentError(
            "PAYPAL_MERCHANT_CHANGED",
            "The configured sandbox merchant differs from this checkout.",
            503,
        )
    if payment and payment.state == "completed":
        db.commit()
        return payment, None, False
    if action == "create":
        if payment and payment.state != "creating":
            db.commit()
            return payment, None, False
        _payable(db, order)
        if payment is None:
            payment = PayPalCheckout(
                order_id=order_id,
                merchant_id=gateway.merchant_id,
                amount_minor=order.subtotal_minor,
                state="creating",
            )
            db.add(payment)
    elif payment is None or payment.provider_order_id is None:
        raise PaymentError("CHECKOUT_NOT_READY", "Create the sandbox checkout first.")
    if action == "capture":
        if payment.state == "ready":
            _payable(db, order)
        elif payment.state != "capture_pending":
            raise PaymentError(
                "PAYPAL_RECONCILE_REQUIRED", "Reconcile this payment before continuing."
            )
    lease = repository.claim(payment)
    first_capture = action == "capture" and payment.capture_started_at is None
    if action == "capture":
        payment.state = "capture_pending"
        if first_capture:
            payment.capture_started_at = utcnow()
    db.commit()
    return payment, lease, first_capture


def _current(db: Session, order_id: str, lease: str) -> tuple[Order, PayPalCheckout]:
    order = repository.lock_order(db, order_id)
    payment = get_checkout(db, order_id)
    if payment.lease_token != lease:
        raise PaymentError(
            "PAYPAL_OPERATION_IN_PROGRESS",
            "The payment operation was superseded; read its current state.",
        )
    return order, payment


def _remember_id(db: Session, order_id: str, lease: str, remote_id: str) -> None:
    _order, payment = _current(db, order_id, lease)
    if payment.provider_order_id and payment.provider_order_id != remote_id:
        raise VerificationError()
    duplicate = db.scalar(
        select(PayPalCheckout).where(
            PayPalCheckout.provider_order_id == remote_id,
            PayPalCheckout.order_id != order_id,
        )
    )
    if duplicate is not None:
        raise VerificationError()
    payment.provider_order_id = remote_id
    db.commit()


def _fetch(payment: PayPalCheckout, gateway: Gateway) -> VerifiedPayment:
    return verify(
        gateway.fetch(payment.provider_order_id),
        payment.order_id,
        payment.provider_order_id,
        payment.merchant_id,
        payment.amount_minor,
    )


def _consume_stock(db: Session, order: Order) -> None:
    snapshot_units = {
        line["listing_id"]: line["listing"]["product"]["selling_unit"]
        for line in order.snapshot["items"]
    }
    for line in repository.lines(db, order.id):
        balance = stock.balance(db, line.product_id, utcnow())
        inventory = db.get(SellableInventory, line.product_id)
        if (
            inventory is None
            or balance.available < 0
            or inventory.on_hand < line.quantity
            or inventory.selling_unit != snapshot_units[line.listing_id]
        ):
            raise VerificationError()
        inventory.on_hand -= line.quantity
        inventory.revision += 1


def _apply(db: Session, order_id: str, lease: str, checked: VerifiedPayment) -> PayPalCheckout:
    order, payment = _current(db, order_id, lease)
    if checked.outcome == "paid":
        if payment.capture_started_at is None or order.status != "pending_payment":
            raise VerificationError()
        duplicate = db.scalar(
            select(PayPalCheckout).where(
                PayPalCheckout.capture_id == checked.capture_id,
                PayPalCheckout.order_id != order_id,
            )
        )
        if duplicate is not None:
            raise VerificationError()
        _consume_stock(db, order)
        payment.state = "completed"
        payment.capture_id = checked.capture_id
        payment.fee_minor = checked.fee_minor
        payment.net_minor = checked.net_minor
        payment.verified_at = utcnow()
    elif checked.outcome == "failed":
        payment.state = "failed"
        order.status = "cancelled"
    elif checked.outcome == "pending":
        payment.state = "capture_pending"
    elif payment.state == "creating":
        payment.state = "ready"
    # An APPROVED read does not prove an uncertain capture did not occur.
    payment.provider_status = checked.provider_status
    repository.release(payment)
    db.commit()
    return payment


def _cleanup(db: Session, order_id: str, lease: str, *, review=False) -> None:
    db.rollback()
    _order, payment = _current(db, order_id, lease)
    if review:
        payment.state = "needs_review"
    repository.release(payment)
    db.commit()


def create(db: Session, buyer_id: str, order_id: str, gateway: Gateway) -> PayPalCheckout:
    payment, lease, _first = _begin(db, buyer_id, order_id, gateway, "create")
    if lease is None:
        return payment
    try:
        if payment.provider_order_id is None:
            remote_id = gateway.create(order_id, payment.amount_minor, payment.create_request_id)
            _remember_id(db, order_id, lease, remote_id)
            payment = get_checkout(db, order_id)
        return _apply(db, order_id, lease, _fetch(payment, gateway))
    except ProviderError:
        _cleanup(db, order_id, lease)
        raise unavailable() from None
    except VerificationError:
        _cleanup(db, order_id, lease, review=True)
        raise PaymentError(
            "PAYPAL_VERIFICATION_FAILED", "The provider response requires payment review.", 502
        ) from None


def capture(db: Session, buyer_id: str, order_id: str, gateway: Gateway) -> PayPalCheckout:
    payment, lease, first_capture = _begin(db, buyer_id, order_id, gateway, "capture")
    if lease is None:
        return payment
    try:
        checked = _fetch(payment, gateway)
        if checked.outcome != "ready":
            return _apply(db, order_id, lease, checked)
        if checked.provider_status != "APPROVED":
            if first_capture:
                _order, current = _current(db, order_id, lease)
                current.state = "ready"
                current.capture_started_at = None
                repository.release(current)
                db.commit()
            else:
                _cleanup(db, order_id, lease)
            raise PaymentError(
                "PAYPAL_APPROVAL_REQUIRED", "The buyer must approve the PayPal order first."
            )
        # Avoid retrying POST after PayPal's documented default six-hour key retention.
        if _utc(payment.capture_started_at) + timedelta(hours=6) <= utcnow():
            _cleanup(db, order_id, lease)
            raise PaymentError(
                "PAYPAL_RECONCILE_REQUIRED",
                "The safe capture retry window elapsed; reconcile instead.",
            )
        try:
            gateway.capture(payment.provider_order_id, payment.capture_request_id)
        except ProviderError:
            # The POST may have succeeded remotely. A verified GET can settle it.
            pass
        checked = _fetch(payment, gateway)
        if checked.outcome == "ready":
            raise ProviderError()
        return _apply(db, order_id, lease, checked)
    except ProviderError:
        _cleanup(db, order_id, lease)
        raise unavailable() from None
    except VerificationError:
        _cleanup(db, order_id, lease, review=True)
        raise PaymentError(
            "PAYPAL_VERIFICATION_FAILED", "The provider response requires payment review.", 502
        ) from None


def reconcile(
    db: Session,
    account_id: str,
    order_id: str,
    gateway: Gateway,
    *,
    seller=False,
) -> PayPalCheckout:
    payment, lease, _first = _begin(db, account_id, order_id, gateway, "reconcile", seller=seller)
    if lease is None:
        return payment
    try:
        return _apply(db, order_id, lease, _fetch(payment, gateway))
    except ProviderError:
        _cleanup(db, order_id, lease)
        raise unavailable() from None
    except VerificationError:
        _cleanup(db, order_id, lease, review=True)
        raise PaymentError(
            "PAYPAL_VERIFICATION_FAILED", "The provider response requires payment review.", 502
        ) from None
