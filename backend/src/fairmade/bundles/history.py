"""Private seller co-purchase counts, never buyer identities or public popularity claims."""

from collections import Counter
from datetime import date, datetime, time, timedelta
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.models import Order, OrderLine, PayPalCheckout, RefundRequest


def counts(
    db: Session, seller_id: str, listing_ids: list[str]
) -> tuple[dict[tuple[str, str], int], date, date]:
    end = utcnow().date()
    start = end - timedelta(days=90)
    orders = list(
        db.scalars(
            select(Order.id)
            .join(PayPalCheckout, PayPalCheckout.order_id == Order.id)
            .where(
                Order.seller_account_id == seller_id,
                Order.buyer_account_id != seller_id,
                PayPalCheckout.state == "completed",
                PayPalCheckout.capture_id.is_not(None),
                PayPalCheckout.verified_at >= datetime.combine(start, time.min),
                PayPalCheckout.verified_at < datetime.combine(end, time.min),
                Order.id.not_in(select(RefundRequest.order_id)),
            )
            .order_by(Order.id)
            .limit(201)
        ).all()
    )
    if len(orders) > 200:
        raise api_error(
            409, "BUNDLE_HISTORY_TOO_LARGE", "Sales exceed the local bundle report limit."
        )
    rows = db.execute(
        select(OrderLine.order_id, OrderLine.listing_id).where(
            OrderLine.order_id.in_(orders), OrderLine.listing_id.in_(listing_ids)
        )
    ).all()
    # At most eight distinct current candidate IDs per bounded order.
    grouped: dict[str, set[str]] = {}
    for order_id, listing_id in rows:
        grouped.setdefault(order_id, set()).add(listing_id)
    result = Counter()
    for identifiers in grouped.values():
        result.update(combinations(sorted(identifiers), 2))
    return dict(result), start, end
