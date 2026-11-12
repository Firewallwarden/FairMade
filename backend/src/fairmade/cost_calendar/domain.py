"""Complete UTC save months, latest snapshots and explicit same-calendar-month comparisons."""

from datetime import date

from fairmade.cost_calendar.records import Snapshot
from fairmade.cost_calendar.schemas import AnnualComparison, CalendarMonthSummary, CostMonth
from fairmade.money_changes import difference


def month_index(day: date) -> int:
    return day.year * 12 + day.month - 1


def month_start(index: int) -> date:
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def months(
    rows: list[Snapshot], start: date, count: int, product_type: str, unit: str
) -> list[CostMonth]:
    grouped: dict[int, list[Snapshot]] = {}
    for row in rows:
        grouped.setdefault(month_index(row.saved_on), []).append(row)
    result = []
    for index in range(month_index(start), month_index(start) + count):
        values = grouped.get(index, [])
        latest = values[-1] if values else None
        compatible = [
            row
            for row in values
            if row.product_type == product_type
            and row.selling_unit == unit
            and row.unit_cost is not None
        ]
        if latest is None:
            status = "missing"
        elif latest.product_type != product_type or latest.selling_unit != unit:
            status = "basis_changed"
        elif latest.unit_cost is None:
            status = "unsupported_snapshot"
        else:
            status = "recorded"
        result.append(
            CostMonth(
                month=month_start(index).strftime("%Y-%m"),
                status=status,
                record_count=len(values),
                compatible_record_count=len(compatible),
                latest_analysis_id=latest.identifier if latest else None,
                latest_saved_on=latest.saved_on if latest else None,
                unit_cost=latest.unit_cost if status == "recorded" else None,
            )
        )
    return result


def annual_comparisons(slots: list[CostMonth]) -> list[AnnualComparison]:
    result = []
    for index in range(12, len(slots)):
        previous, current = slots[index - 12], slots[index]
        comparable = previous.status == current.status == "recorded"
        result.append(
            AnnualComparison(
                previous_month=previous.month,
                current_month=current.month,
                previous_analysis_id=previous.latest_analysis_id,
                current_analysis_id=current.latest_analysis_id,
                status="comparable" if comparable else "missing_or_incompatible",
                difference=difference(previous.unit_cost, current.unit_cost),
            )
        )
    return result


def by_calendar_month(slots: list[CostMonth]) -> list[CalendarMonthSummary]:
    result = []
    for month in range(1, 13):
        values = [row for row in slots if row.status == "recorded" and int(row.month[5:]) == month]
        costs = [row.unit_cost for row in values]
        result.append(
            CalendarMonthSummary(
                calendar_month=month,
                observed_years=[int(row.month[:4]) for row in values],
                minimum_unit_cost=min(costs) if costs else None,
                maximum_unit_cost=max(costs) if costs else None,
            )
        )
    return result
