"""Snapshot arithmetic without payment, HTTP or database dependencies."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

from fairmade.pricing.costs import production_costs
from fairmade.pricing.schemas import PricingRequest

CENT = Decimal("0.01")
DETAIL = Decimal("0.000001")


@dataclass(frozen=True)
class OrderCostLine:
    listing_id: str
    product_id: str
    quantity: int
    selling_unit: str
    product_type: str


def cost_source(inputs: dict, product: dict, analysis_id: str, created_at: str) -> dict:
    request = PricingRequest.model_validate(inputs)
    costs = production_costs(request)
    with localcontext() as context:
        context.prec = 60
        return {
            "cost_version": "sales-cost-basis-v1",
            "calculation_version": "production-economics-v1",
            "basis": "seller_supplied_unverified",
            "analysis_id": analysis_id,
            "analysis_created_at": created_at,
            "selling_unit": product["selling_unit"],
            "product_type": product["product_type"],
            "batch_production_cost": str(costs.batch_total),
            "sellable_units": request.sellable_units,
            "display_unit_cost": str(
                (costs.batch_total / request.sellable_units).quantize(
                    DETAIL, rounding=ROUND_HALF_UP
                )
            ),
            "warnings": [
                code
                for missing, code in (
                    (not costs.labor_total, "NO_LABOR_COST"),
                    (
                        not any(
                            costs.category_totals[key]
                            for key in ("utilities", "equipment", "overhead")
                        ),
                        "NO_OVERHEAD_COST",
                    ),
                )
                if missing
            ],
        }


def source_matches(source: dict | None, selling_unit: str, product_type: str) -> bool:
    return (
        source is not None
        and source.get("cost_version") == "sales-cost-basis-v1"
        and source.get("selling_unit") == selling_unit
        and source.get("product_type") == product_type
    )


def total_production_cost(items: list[dict]) -> Decimal | None:
    if any(item["unavailable_reason"] is not None for item in items):
        return None
    total = sum(
        (
            Fraction(Decimal(item["source"]["batch_production_cost"]))
            * item["quantity"]
            / item["source"]["sellable_units"]
            for item in items
        ),
        Fraction(0),
    )
    # Keep repeating unit ratios exact; round half up once for the whole order.
    minor_units, remainder = divmod(total.numerator * 100, total.denominator)
    if remainder * 2 >= total.denominator:
        minor_units += 1
    with localcontext() as context:
        context.prec = 60
        return Decimal(minor_units).scaleb(-2).quantize(CENT)
