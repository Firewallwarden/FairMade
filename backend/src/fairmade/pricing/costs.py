"""Exact production costs shared by pricing scenarios and private sales estimates."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext

from fairmade.pricing.schemas import BatchCost, CostCategory, Labor, PricingRequest


@dataclass(frozen=True)
class ProductionCosts:
    category_totals: dict[CostCategory, Decimal]
    labor_total: Decimal
    batch_total: Decimal


def production_costs(request: PricingRequest) -> ProductionCosts:
    return sum_production_costs(request.costs, request.labor)


def sum_production_costs(costs: Sequence[BatchCost], labor: Sequence[Labor]) -> ProductionCosts:
    # Do not mix the pricing model's estimated payment fees into production cost.
    with localcontext() as context:
        context.prec = 60
        totals = dict.fromkeys(CostCategory, Decimal(0))
        for cost in costs:
            totals[cost.category] += cost.amount
        labor_total = sum((item.hours * item.hourly_rate for item in labor), Decimal(0))
        return ProductionCosts(totals, labor_total, sum(totals.values(), labor_total))
