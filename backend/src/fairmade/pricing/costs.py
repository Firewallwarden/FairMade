"""Exact production costs shared by pricing scenarios and private sales estimates."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from fairmade.pricing.schemas import CostCategory, PricingRequest


@dataclass(frozen=True)
class ProductionCosts:
    category_totals: dict[CostCategory, Decimal]
    labor_total: Decimal
    batch_total: Decimal


def production_costs(request: PricingRequest) -> ProductionCosts:
    # Do not mix the pricing model's estimated payment fees into production cost.
    with localcontext() as context:
        context.prec = 60
        totals = dict.fromkeys(CostCategory, Decimal(0))
        for cost in request.costs:
            totals[cost.category] += cost.amount
        labor = sum((item.hours * item.hourly_rate for item in request.labor), Decimal(0))
        return ProductionCosts(totals, labor, sum(totals.values(), labor))
