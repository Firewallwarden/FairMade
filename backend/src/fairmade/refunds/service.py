"""Buyer requests, immutable seller decisions and retry-safe sandbox refund execution."""

from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.leases import release_lease
from fairmade.models import Order, PayPalCheckout, RefundRequest
from fairmade.orders.domain import money
from fairmade.payments.errors import ProviderError, VerificationError
from fairmade.refunds import repository, verification
from fairmade.refunds.errors import RefundError, missing
from fairmade.refunds.gateway import RefundGateway
from fairmade.refunds.schemas import ApproveRequest, CreateRequest, DenyRequest, RefundResponse


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def owned_order(db: Session, account_id: str, order_id: str, *, seller=False) -> Order:
    order = db.scalar(
        repository.owned_orders(account_id, seller=seller).where(Order.id == order_id)
    )
    if order is None:
        raise missing()
    return order


def get_request(db: Session, order_id: str) -> RefundRequest:
    request = repository.for_order(db, order_id)
    if request is None:
        raise missing()
    return request


def response(request: RefundRequest) -> RefundResponse:
    return RefundResponse(
        id=request.id,
        order_id=request.order_id,
        revision=request.revision,
        state=request.state,
        reason=request.reason,
        created_at=request.created_at,
        decision=request.decision,
        decision_reason=request.decision_reason,
        decision_expected_revision=request.decision_revision,
        decided_at=request.decided_at,
        amount=money(request.amount_minor),
        provider_refund_id=request.provider_refund_id,
        provider_status=request.provider_status,
        verified_at=request.verified_at,
    )


def create(
    db: Session,
    buyer_id: str,
    order_id: str,
    body: CreateRequest,
) -> tuple[RefundRequest, bool]:
    owned_order(db, buyer_id, order_id)
    repository.lock_order(db, order_id)
    existing = repository.for_order(db, order_id)
    if existing is not None:
        if existing.reason != body.reason:
            raise RefundError("REFUND_REQUEST_EXISTS", "This order already has a refund request.")
        db.commit()
        return existing, False
    payment = db.get(PayPalCheckout, order_id)
    if payment is None or payment.state != "completed" or not payment.capture_id:
        raise RefundError("ORDER_NOT_PAID", "Only a verified paid order can have a refund request.")
    request = RefundRequest(
        order_id=order_id,
        requested_by_account_id=buyer_id,
        reason=body.reason,
        revision=1,
        state="requested",
        amount_minor=payment.amount_minor,
        merchant_id=payment.merchant_id,
        capture_id=payment.capture_id,
        provider_order_id=payment.provider_order_id,
    )
    db.add(request)
    db.commit()
    return request, True


def deny(db: Session, seller_id: str, order_id: str, body: DenyRequest) -> RefundRequest:
    owned_order(db, seller_id, order_id, seller=True)
    repository.lock_order(db, order_id)
    request = get_request(db, order_id)
    if request.decision is not None:
        if (
            request.decision == "denied"
            and request.decision_reason == body.reason
            and request.decision_revision == body.expected_revision
        ):
            db.commit()
            return request
        raise RefundError(
            "REFUND_ALREADY_DECIDED", "This refund request already has a seller decision."
        )
    if request.revision != body.expected_revision:
        raise RefundError("REVISION_CONFLICT", "The refund request revision has changed.")
    request.decision = "denied"
    request.decision_reason = body.reason
    request.decision_revision = body.expected_revision
    request.decided_by_account_id = seller_id
    request.decided_at = utcnow()
    request.state = "denied"
    request.revision += 1
    db.commit()
    return request


def _begin(
    db: Session,
    account_id: str,
    order_id: str,
    gateway: RefundGateway,
    approval: ApproveRequest | None,
    *,
    seller: bool,
) -> tuple[RefundRequest, str | None, bool]:
    owned_order(db, account_id, order_id, seller=seller)
    repository.lock_order(db, order_id)
    request = get_request(db, order_id)
    if request.merchant_id != gateway.merchant_id:
        raise RefundError(
            "REFUND_MERCHANT_CHANGED",
            "The configured sandbox merchant differs from this payment.",
            503,
        )
    if approval is not None:
        if not seller:
            raise RefundError("SELLER_REQUIRED", "Seller approval is required.", 403)
        if request.decision is None:
            if request.revision != approval.expected_revision:
                raise RefundError("REVISION_CONFLICT", "The refund request revision has changed.")
            request.decision = "approved"
            request.decision_revision = approval.expected_revision
            request.decided_by_account_id = account_id
            request.decided_at = utcnow()
            request.state = "refund_pending"
            request.revision += 1
        elif (
            request.decision != "approved"
            or request.decision_revision != approval.expected_revision
        ):
            raise RefundError(
                "REFUND_ALREADY_DECIDED", "This refund request already has a seller decision."
            )
    elif request.decision != "approved":
        db.commit()
        return request, None, False
    if request.state in ("refunded", "failed"):
        db.commit()
        return request, None, False
    if request.state == "needs_review" and request.provider_refund_id is None:
        raise RefundError(
            "REFUND_REVIEW_REQUIRED", "The refund needs review before another provider operation."
        )
    if approval is None and request.provider_refund_id is None:
        raise RefundError(
            "REFUND_RESULT_UNKNOWN",
            "The refund result is unavailable; seller retry or review is required.",
        )
    payment = db.get(PayPalCheckout, order_id)
    if (
        payment is None
        or payment.state != "completed"
        or payment.capture_id != request.capture_id
        or payment.amount_minor != request.amount_minor
        or payment.merchant_id != request.merchant_id
    ):
        raise RefundError("REFUND_REVIEW_REQUIRED", "The original payment requires review.")
    lease = repository.claim(request)
    first_attempt = request.attempted_at is None
    if first_attempt:
        request.attempted_at = utcnow()
    db.commit()
    return request, lease, first_attempt


def _current(db: Session, order_id: str, lease: str) -> RefundRequest:
    repository.lock_order(db, order_id)
    request = get_request(db, order_id)
    if request.lease_token != lease:
        raise RefundError(
            "REFUND_OPERATION_IN_PROGRESS", "The operation was superseded; read its current state."
        )
    return request


def _remember_id(db: Session, order_id: str, lease: str, remote_id: str) -> None:
    request = _current(db, order_id, lease)
    if request.provider_refund_id and request.provider_refund_id != remote_id:
        raise VerificationError()
    duplicate = db.scalar(
        select(RefundRequest).where(
            RefundRequest.provider_refund_id == remote_id,
            RefundRequest.order_id != order_id,
        )
    )
    if duplicate is not None:
        raise VerificationError()
    request.provider_refund_id = remote_id
    db.commit()


def _capture_status(request: RefundRequest, gateway: RefundGateway) -> str:
    return verification.capture_status(
        gateway.fetch_capture(request.capture_id),
        request.capture_id,
        request.merchant_id,
        request.provider_order_id,
        request.amount_minor,
    )


def _settle(db: Session, order_id: str, lease: str, status: str) -> RefundRequest:
    request = _current(db, order_id, lease)
    next_state = {"COMPLETED": "refunded", "PENDING": "refund_pending"}.get(status, "failed")
    if request.state != next_state or request.provider_status != status:
        request.revision += 1
    request.state = next_state
    request.provider_status = status
    if status == "COMPLETED":
        request.verified_at = utcnow()
    release_lease(request)
    db.commit()
    return request


def _cleanup(db: Session, order_id: str, lease: str, *, review=False) -> None:
    db.rollback()
    request = _current(db, order_id, lease)
    if review and request.state != "needs_review":
        request.state = "needs_review"
        request.revision += 1
    release_lease(request)
    db.commit()


def _execute(
    db: Session,
    request: RefundRequest,
    lease: str,
    gateway: RefundGateway,
    *,
    allow_post: bool,
    first_attempt: bool,
) -> RefundRequest:
    order_id = request.order_id
    try:
        status = _capture_status(request, gateway)
        if request.provider_refund_id is None:
            if not allow_post:
                raise RefundError(
                    "REFUND_RESULT_UNKNOWN", "The refund result requires seller retry or review."
                )
            if _utc(request.attempted_at) + timedelta(hours=6) <= utcnow():
                _cleanup(db, order_id, lease, review=True)
                raise RefundError(
                    "REFUND_RETRY_WINDOW_ELAPSED",
                    "Only reconciliation or manual review is allowed now.",
                )
            if status != "COMPLETED" and (first_attempt or status != "REFUNDED"):
                raise VerificationError()
            remote_id = gateway.refund(
                request.capture_id,
                request.id,
                request.amount_minor,
                request.provider_request_id,
            )
            _remember_id(db, order_id, lease, remote_id)
            request = get_request(db, order_id)
        data = gateway.fetch_refund(request.provider_refund_id)
        status = verification.refund_status(
            data,
            request.provider_refund_id,
            request.id,
            request.capture_id,
            request.amount_minor,
        )
        return _settle(db, order_id, lease, status)
    except ProviderError:
        _cleanup(db, order_id, lease)
        raise RefundError(
            "REFUND_PROVIDER_UNAVAILABLE",
            "The refund result is unavailable; retry or reconcile safely.",
            502,
        ) from None
    except VerificationError:
        _cleanup(db, order_id, lease, review=True)
        raise RefundError(
            "REFUND_VERIFICATION_FAILED", "The provider response requires refund review.", 502
        ) from None


def approve(
    db: Session,
    seller_id: str,
    order_id: str,
    body: ApproveRequest,
    gateway: RefundGateway,
) -> RefundRequest:
    request, lease, first = _begin(db, seller_id, order_id, gateway, body, seller=True)
    if lease is None:
        return request
    return _execute(db, request, lease, gateway, allow_post=True, first_attempt=first)


def reconcile(
    db: Session,
    account_id: str,
    order_id: str,
    gateway: RefundGateway,
    *,
    seller=False,
) -> RefundRequest:
    request, lease, first = _begin(db, account_id, order_id, gateway, None, seller=seller)
    if lease is None:
        return request
    return _execute(db, request, lease, gateway, allow_post=False, first_attempt=first)
