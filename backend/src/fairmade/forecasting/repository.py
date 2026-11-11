"""Only verified, seller-owned product sales; never fetch buyer or provider identity."""

from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.forecasting.records import SaleObservation
from fairmade.models import Order, OrderLine, PayPalCheckout, RefundRequest

MAX_LINES = 1000


def observations(
    db: Session, seller_id: str, product_id: str, start: date, end: date
) -> list[SaleObservation]:
    rows = db.execute(
        select(
            PayPalCheckout.verified_at,
            Order.created_at,
            OrderLine.quantity,
            OrderLine.listing_id,
            Order.snapshot,
            RefundRequest.order_id,
        )
        .select_from(OrderLine)
        .join(Order, Order.id == OrderLine.order_id)
        .join(PayPalCheckout, PayPalCheckout.order_id == Order.id)
        .outerjoin(RefundRequest, RefundRequest.order_id == Order.id)
        .where(
            Order.seller_account_id == seller_id,
            OrderLine.product_id == product_id,
            PayPalCheckout.state == "completed",
            PayPalCheckout.capture_id.is_not(None),
            PayPalCheckout.verified_at >= datetime.combine(start, time.min),
            PayPalCheckout.verified_at < datetime.combine(end, time.min),
        )
        .order_by(PayPalCheckout.verified_at, OrderLine.id)
        .limit(MAX_LINES + 1)
    ).all()
    if len(rows) > MAX_LINES:
        raise api_error(409, "FORECAST_SCOPE_TOO_LARGE", "Narrow the forecast lookback window.")
    result = []
    for captured, ordered, quantity, listing_id, snapshot, refund_id in rows:
        # This immutable snapshot contains approved public catalog data only.
        # Missing/changed historical units are excluded, never relabeled as current units.
        matches = [
            item for item in snapshot.get("items", []) if item.get("listing_id") == listing_id
        ]
        product = matches[0].get("listing", {}).get("product", {}) if len(matches) == 1 else {}
        result.append(
            SaleObservation(
                captured_at=captured,
                ordered_at=ordered,
                quantity=quantity,
                product_type=product.get("product_type"),
                selling_unit=product.get("selling_unit"),
                has_refund_request=refund_id is not None,
            )
        )
    return result
