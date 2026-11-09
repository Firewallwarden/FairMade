"""Strict pickup transitions, exact retry handling and payment/refund gates."""

from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.fulfillment import repository
from fairmade.fulfillment.schemas import PickupEvent, PickupResponse, PickupUpdate
from fairmade.models import Order, PickupFulfillmentEvent

NOTICES = [
    "Pickup progress and instructions are private seller reports, not verified handoff proof.",
    "Fulfillment does not confirm payment, change stock, approve refunds or restock returns.",
    "No delivery, shipping, delivery fees or buyer delivery addresses are configured.",
]
NEXT_STATE = {
    "not_started": "preparing",
    "preparing": "ready_for_pickup",
    "ready_for_pickup": "collected",
}


def error(status: int, code: str, message: str):
    result = api_error(status, code, message)
    result.headers = {"Cache-Control": "no-store"}
    return result


def require_order(db: Session, account_id: str, order_id: str, *, seller: bool) -> Order:
    order = repository.owned_order(db, account_id, order_id, seller=seller)
    if order is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return order


def verified_paid(order: Order) -> bool:
    payment = order.checkout
    return bool(
        payment and payment.state == "completed" and payment.capture_id and payment.verified_at
    )


def refund_blocks(order: Order) -> bool:
    refund = order.refund_request
    return bool(
        refund
        and (
            refund.state in ("requested", "refund_pending", "needs_review", "refunded")
            or refund.decision == "approved"
        )
    )


def response(order: Order, event: PickupFulfillmentEvent | None) -> PickupResponse:
    return PickupResponse(
        order_id=order.id,
        revision=event.revision if event else 0,
        state=event.state if event else "not_started",
        pickup_instructions=event.pickup_instructions if event else None,
        latest_event=PickupEvent.model_validate(event) if event else None,
        updates_allowed=verified_paid(order)
        and not refund_blocks(order)
        and (event is None or event.state != "collected"),
        notices=NOTICES,
    )


def get(db: Session, account_id: str, order_id: str, *, seller: bool) -> PickupResponse:
    order = require_order(db, account_id, order_id, seller=seller)
    return response(order, repository.latest(db, order.id))


def update(db: Session, account_id: str, order_id: str, body: PickupUpdate) -> PickupResponse:
    require_order(db, account_id, order_id, seller=True)
    repository.lock_order(db, account_id, order_id)
    order = require_order(db, account_id, order_id, seller=True)
    if not verified_paid(order):
        raise error(409, "ORDER_NOT_PAID", "Pickup updates require a backend-verified paid order.")
    if refund_blocks(order):
        raise error(
            409, "REFUND_BLOCKS_FULFILLMENT", "Resolve the refund before further pickup updates."
        )
    current = repository.latest(db, order.id)
    revision = current.revision if current else 0
    state = current.state if current else "not_started"
    same_content = bool(
        current
        and current.state == body.state
        and current.pickup_instructions == body.pickup_instructions
    )
    if same_content and body.expected_revision in (revision, revision - 1):
        db.commit()
        return response(order, current)
    if body.expected_revision != revision:
        raise error(409, "REVISION_CONFLICT", "Pickup progress changed; reload before retrying.")
    if state == "collected" or (body.state != state and NEXT_STATE.get(state) != body.state):
        raise error(
            409, "INVALID_PICKUP_TRANSITION", "Follow preparing, ready for pickup, then collected."
        )
    event = PickupFulfillmentEvent(
        order_id=order.id,
        revision=revision + 1,
        state=body.state,
        pickup_instructions=body.pickup_instructions,
        recorded_by_account_id=account_id,
    )
    db.add(event)
    db.commit()
    return response(order, event)
