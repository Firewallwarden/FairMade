"""Join live quantities/filtering in the same query as catalog visibility."""

from sqlalchemy import and_, case, func, select

from fairmade.availability.schemas import AvailabilityStatus, ListingAvailability
from fairmade.database import utcnow
from fairmade.models import MarketplaceListing, Order, OrderLine, PayPalCheckout, SellableInventory
from fairmade.stock import active_hold_conditions


def with_availability(statement, availability: AvailabilityStatus | None = None):
    now = utcnow()
    reservations = (
        select(OrderLine.product_id, func.sum(OrderLine.quantity).label("reserved"))
        .join(Order, Order.id == OrderLine.order_id)
        .outerjoin(PayPalCheckout, PayPalCheckout.order_id == Order.id)
        .where(*active_hold_conditions(now))
        .group_by(OrderLine.product_id)
        .subquery()
    )
    inventory = SellableInventory
    unit = MarketplaceListing.public_payload["product"]["selling_unit"].as_string()
    remaining = inventory.on_hand - func.coalesce(reservations.c.reserved, 0)
    known = and_(
        inventory.product_id.is_not(None),
        inventory.revision > 0,
        inventory.selling_unit == unit,
        remaining >= 0,
    )
    status = case(
        (and_(known, remaining > 0), "available"),
        (and_(known, remaining == 0), "unavailable"),
        else_="unknown",
    )
    statement = (
        statement.outerjoin(inventory, inventory.product_id == MarketplaceListing.product_id)
        .outerjoin(reservations, reservations.c.product_id == MarketplaceListing.product_id)
        .add_columns(
            status.label("availability_status"),
            case((known, remaining), else_=None).label("available_units"),
            unit.label("availability_unit"),
        )
    )
    if availability is not None:
        statement = statement.where(status == availability)
    return statement


def public_availability(row) -> ListingAvailability:
    return ListingAvailability(
        status=row.availability_status,
        available_units=row.available_units,
        selling_unit=row.availability_unit,
    )
