"""Owner-only calendar report; historical model snapshots do not establish actual seasonality."""

from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.cost_calendar import domain, repository
from fairmade.cost_calendar.schemas import CalendarOptions, CostCalendar
from fairmade.evidence import today
from fairmade.ownership import require_owned_product

NOTICES = [
    "Complete UTC save months only; the current incomplete month is excluded.",
    "The latest saved snapshot per month represents its modeled basis, not average actual cost.",
    "Save dates are not cost occurrence dates; "
    "model, yield and allocation changes can alter values.",
    "Only current product-type/selling-unit compatible, supported USD snapshots enter comparisons.",
    "Same type/unit labels do not establish equivalent ingredients or quality across snapshots.",
    "An incompatible or unsupported latest snapshot is not replaced by an older convenient value.",
    "Missing months, including periods before product creation, do not establish zero actual cost.",
    "Same-calendar-month differences are descriptive; no inflation, cause, validated seasonal "
    "effect, future demand or future price is inferred.",
    "Calendar-month minima/maxima use latest saved monthly snapshots, not a representative sample.",
    "No record, price, stock, quality requirement, forecast or publication is changed.",
]


def load(db: Session, account_id: str, product_id: str, options: CalendarOptions) -> CostCalendar:
    product = require_owned_product(db, account_id, product_id)
    as_of = today()
    end = domain.month_start(domain.month_index(as_of))
    start = domain.month_start(domain.month_index(end) - options.months)
    records = repository.observations(db, product.id, start, end)
    slots = domain.months(
        records, start, options.months, product.product_type, product.selling_unit
    )
    annual = domain.annual_comparisons(slots)
    available = any(row.status == "comparable" for row in annual)
    return CostCalendar(
        product_id=product.id,
        product_created_on=product.created_at.date(),
        as_of_date=as_of,
        start_date=start,
        end_date=end,
        selling_unit=product.selling_unit,
        requested_months=options.months,
        recorded_months=sum(row.status == "recorded" for row in slots),
        total_snapshots=len(records),
        calendar_evidence_status="descriptive_comparisons_available"
        if available
        else "insufficient_history",
        months=slots,
        year_over_year=annual,
        calendar_month_summaries=domain.by_calendar_month(slots),
        notices=NOTICES,
    )


def report(db: Session, account_id: str, product_id: str, options: CalendarOptions) -> CostCalendar:
    original = load(db, account_id, product_id, options)
    db.expire_all()
    current = load(db, account_id, product_id, options)
    if current != original:
        raise api_error(409, "COST_CALENDAR_CHANGED", "Cost history changed; try again.")
    return current
