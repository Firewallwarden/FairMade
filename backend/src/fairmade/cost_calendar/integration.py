"""Qualitative calendar interpretation and exact owner-only cost history facts."""

from decimal import Decimal

from fairmade.assistants.schemas import Evidence, Paragraph

TITLE = "Private saved cost calendar and annual comparisons"
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def change_direction(value: str | None) -> str:
    if value is None:
        return "unknown"
    delta = Decimal(value)
    if delta > 0:
        return "increased"
    if delta < 0:
        return "decreased"
    return "unchanged"


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    data = fact.data
    comparisons = []
    for row in data["year_over_year"]:
        direction = change_direction(row["difference"]["change"])
        comparisons.append(
            {
                "calendar_month": MONTH_NAMES[int(row["current_month"][5:]) - 1],
                "comparable": row["status"] == "comparable",
                "modeled_direction": direction,
            }
        )
    return {
        "calendar_evidence_status": data["calendar_evidence_status"],
        "seasonality_status": data["seasonality_status"],
        "all_months_have_supported_snapshots": data["recorded_months"] == data["requested_months"],
        "year_over_year": comparisons,
        "policy": data["notices"],
    }


def statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    data = fact.data
    unit = data["selling_unit"]
    texts = [
        f"Saved cost calendar from {data['start_date']} to exclusive {data['end_date']}: "
        f"{data['recorded_months']} supported latest monthly snapshots among "
        f"{data['requested_months']} complete UTC months; "
        f"{data['total_snapshots']} saved analyses.",
        "Save-time models do not establish actual spending, inflation, "
        "causes or validated seasonality. "
        "Missing months are unknown, not zero costs.",
    ]
    for row in data["months"]:
        if row["status"] == "recorded":
            texts.append(
                f"{row['month']}: latest snapshot saved on {row['latest_saved_on']} models "
                f"unit cost USD {row['unit_cost']} per {unit}; "
                f"{row['record_count']} saved snapshots in this month."
            )
    for row in data["year_over_year"]:
        if row["status"] == "comparable":
            change = row["difference"]
            relative = change["relative_change"]
            relative_text = relative if relative is not None else "undefined at zero baseline"
            texts.append(
                f"Same-calendar-month modeled unit cost, {row['previous_month']} to "
                f"{row['current_month']}: change USD {change['change']}; "
                f"fractional relative change {relative_text}. "
                "This comparison is not a seasonal effect or expense-cause finding."
            )
    for summary in data["calendar_month_summaries"]:
        if len(summary["observed_years"]) >= 2:
            texts.append(
                f"Recorded {MONTH_NAMES[summary['calendar_month'] - 1]} latest monthly snapshots "
                f"across years {', '.join(str(year) for year in summary['observed_years'])}: "
                f"modeled unit costs USD {summary['minimum_unit_cost']} to "
                f"{summary['maximum_unit_cost']}. No validated seasonal conclusion."
            )
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
