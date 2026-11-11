"""Bounded product-owned projections; raw costs, labels, labor and notes are not selected."""

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.cost_calendar.records import Snapshot
from fairmade.models import Analysis


def supported_cost(version, result_version, currency, value) -> Decimal | None:
    if (
        version != "production-economics-v1"
        or result_version != version
        or currency != "USD"
        or not isinstance(value, str)
        or len(value) > 100
    ):
        return None
    try:
        cost = Decimal(value)
    except InvalidOperation:
        return None
    supported = cost.is_finite() and cost >= 0 and cost.adjusted() <= 30
    if supported and -6 <= cost.as_tuple().exponent <= 30:
        return cost
    return None


def observations(db: Session, product_id: str, start: date, end: date) -> list[Snapshot]:
    rows = db.execute(
        select(
            Analysis.id,
            Analysis.created_at,
            Analysis.product_snapshot["product_type"].as_string(),
            Analysis.product_snapshot["selling_unit"].as_string(),
            Analysis.calculation_version,
            Analysis.result["calculation_version"].as_string(),
            Analysis.result["currency"].as_string(),
            Analysis.result["costs"]["unit_cost"].as_string(),
        )
        .where(
            Analysis.product_id == product_id,
            Analysis.created_at >= datetime.combine(start, time.min),
            Analysis.created_at < datetime.combine(end, time.min),
        )
        .order_by(Analysis.created_at, Analysis.id)
        .limit(1001)
    ).all()
    if len(rows) > 1000:
        raise api_error(409, "COST_CALENDAR_TOO_LARGE", "Narrow the calendar period.")
    return [
        Snapshot(
            identifier,
            created.date(),
            kind,
            unit,
            supported_cost(version, result_version, currency, cost),
        )
        for identifier, created, kind, unit, version, result_version, currency, cost in rows
    ]
