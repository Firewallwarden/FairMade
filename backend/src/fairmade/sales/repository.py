"""Indexed capture-cohort queries; one row per seller-owned order."""

from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.models import Order, OrderSalesCostSnapshot, PayPalCheckout, RefundRequest
from fairmade.sales.records import SaleRecord

MAX_SUMMARY_ORDERS = 1000


def _query(seller_id: str, start_date: date, end_date: date, *, include_snapshots: bool):
    fields = [
        Order.id.label("order_id"),
        Order.created_at.label("created_at"),
        PayPalCheckout.verified_at.label("captured_at"),
        PayPalCheckout.amount_minor.label("gross_minor"),
        PayPalCheckout.fee_minor.label("fee_minor"),
        PayPalCheckout.net_minor.label("net_minor"),
        RefundRequest.state.label("refund_state"),
        RefundRequest.amount_minor.label("refund_minor"),
        RefundRequest.verified_at.label("refund_verified_at"),
        OrderSalesCostSnapshot.status.label("cost_status"),
        OrderSalesCostSnapshot.estimated_cost.label("cost_total"),
    ]
    if include_snapshots:
        fields.append(OrderSalesCostSnapshot.details.label("cost_details"))
    return (
        select(*fields)
        .select_from(Order)
        .join(PayPalCheckout, PayPalCheckout.order_id == Order.id)
        .outerjoin(RefundRequest, RefundRequest.order_id == Order.id)
        .outerjoin(OrderSalesCostSnapshot, OrderSalesCostSnapshot.order_id == Order.id)
        .where(
            Order.seller_account_id == seller_id,
            PayPalCheckout.state == "completed",
            PayPalCheckout.capture_id.is_not(None),
            PayPalCheckout.verified_at >= datetime.combine(start_date, time.min),
            PayPalCheckout.verified_at < datetime.combine(end_date, time.min),
        )
        .order_by(PayPalCheckout.verified_at.desc(), Order.id.desc())
    )


def summary_records(
    db: Session, seller_id: str, start_date: date, end_date: date
) -> list[SaleRecord]:
    rows = db.execute(
        _query(seller_id, start_date, end_date, include_snapshots=False).limit(
            MAX_SUMMARY_ORDERS + 1
        )
    ).mappings()
    return [SaleRecord(**row) for row in rows]


def page_records(
    db: Session, seller_id: str, start_date: date, end_date: date, limit: int, offset: int
) -> list[SaleRecord]:
    rows = db.execute(
        _query(seller_id, start_date, end_date, include_snapshots=True).limit(limit).offset(offset)
    ).mappings()
    return [SaleRecord(**row) for row in rows]
