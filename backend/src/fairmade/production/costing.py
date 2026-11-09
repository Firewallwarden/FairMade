"""Exact completed-production costs without invented pricing preferences."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from fairmade.pricing.costs import sum_production_costs
from fairmade.pricing.schemas import CostCategory
from fairmade.production.schemas import ProductionRequest, ProductionResult

DETAIL = Decimal("0.000001")


def calculate_completed(body: ProductionRequest) -> ProductionResult:
    with localcontext() as context:
        context.prec = 60
        costs = sum_production_costs(body.costs, body.labor)
        warnings = [
            "Output and allocated costs are unverified seller reports, not verified expenses.",
            "An empty or zero cost category does not prove that no expense occurred.",
            "Use consumed costs including waste; avoid duplicate labor or whole-package spending.",
            "No stock, sales revenue, payment fees, market or Quality Lock claims are evaluated.",
        ]
        if body.sellable_units == 0:
            warnings.append("ZERO_SELLABLE_YIELD: cost per sellable unit is unknown.")
        if not costs.labor_total:
            warnings.append("NO_LABOR_COST: no labor compensation was recorded.")
        if not any(
            costs.category_totals[category]
            for category in (CostCategory.UTILITIES, CostCategory.EQUIPMENT, CostCategory.OVERHEAD)
        ):
            warnings.append("NO_OVERHEAD_COST: no utilities, equipment or overhead was recorded.")
        if not costs.category_totals[CostCategory.MATERIALS]:
            warnings.append("NO_MATERIAL_COST: no material cost was recorded.")

        def rounded(value: Decimal) -> Decimal:
            return value.quantize(DETAIL, rounding=ROUND_HALF_UP)

        return ProductionResult(
            category_totals={key: rounded(value) for key, value in costs.category_totals.items()},
            labor_total=rounded(costs.labor_total),
            batch_total=rounded(costs.batch_total),
            unit_cost=rounded(costs.batch_total / body.sellable_units)
            if body.sellable_units
            else None,
            unsellable_units=body.total_units - body.sellable_units,
            yield_fraction=rounded(Decimal(body.sellable_units) / body.total_units)
            if body.total_units
            else None,
            warnings=warnings,
        )
