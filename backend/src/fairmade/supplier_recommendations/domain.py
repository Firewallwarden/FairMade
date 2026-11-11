"""Explicit cost/preference selection with ties; never an overall quality score."""

from uuid import UUID

from fairmade.quality.service import evaluate
from fairmade.supplier_recommendations.schemas import RecommendationOptions, RecommendationRow
from fairmade.suppliers.schemas import SupplierComparisonRow


def projection(row: SupplierComparisonRow, options: RecommendationOptions) -> RecommendationRow:
    checks = evaluate(options.preferences, row.details.claims).checks
    for check in checks:
        if check.reason_code == "MISSING_CLAIM":
            check.message = (
                "No claim was supplied for this optional preference; its value is unknown."
            )
    eligible = row.eligible_for_cost_comparison
    cost = row.cost if eligible else None
    objective = None
    if cost is not None:
        objective = (
            cost.purchase_cost
            if options.cost_objective == "purchase_outlay"
            else (cost.cost_per_usable_unit)
        )
    return RecommendationRow(
        quote_id=row.quote_id,
        supplier_name=row.details.supplier_name,
        observed_on=row.details.observed_on,
        source=row.details.source,
        mandatory_checks=row.quality.checks,
        preference_checks=checks,
        eligible=eligible,
        exclusion_reasons=row.exclusion_reasons,
        cost=cost,
        objective_cost=objective,
        preference_matches=[check.status == "passed" for check in checks],
        selected_for_input_review=False,
        selection_reason="not_selected" if eligible else "excluded",
    )


def dominates(left: RecommendationRow, right: RecommendationRow) -> bool:
    """Balanced: no higher cost and no fewer matches on ANY optional preference."""
    no_worse_cost = left.objective_cost <= right.objective_cost
    no_worse_preferences = all(
        a >= b for a, b in zip(left.preference_matches, right.preference_matches, strict=True)
    )
    strictly_better = (
        left.objective_cost < right.objective_cost
        or left.preference_matches != right.preference_matches
    )
    return no_worse_cost and no_worse_preferences and strictly_better


def select(rows: list[RecommendationRow], options: RecommendationOptions) -> list[UUID]:
    eligible = [row for row in rows if row.eligible and row.objective_cost is not None]
    if not eligible:
        return []
    if options.mode == "savings":
        minimum = min(row.objective_cost for row in eligible)
        selected = [row for row in eligible if row.objective_cost == minimum]
    elif options.mode == "quality":
        # Order in the request is seller priority, never an invented weighting or grade scale.
        best = max(tuple(row.preference_matches) for row in eligible)
        matches = [row for row in eligible if tuple(row.preference_matches) == best]
        minimum = min(row.objective_cost for row in matches)
        selected = [row for row in matches if row.objective_cost == minimum]
    else:
        selected = [
            row
            for row in eligible
            if not any(dominates(other, row) for other in eligible if other is not row)
        ]
    for row in selected:
        row.selected_for_input_review = True
        row.selection_reason = "selected"
    return sorted((row.quote_id for row in selected), key=str)
