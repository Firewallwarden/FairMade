"""Deterministic economics. No price changes, AI calls, or payment side effects."""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext

from fairmade.pricing.schemas import (
    CostBreakdown,
    CostCategory,
    PriceRange,
    PriceScenario,
    PricingRequest,
    PricingResponse,
    Warning,
)

ZERO = Decimal(0)
ONE = Decimal(1)
CENT = Decimal("0.01")
DETAIL = Decimal("0.000001")


def detail(value: Decimal) -> Decimal:
    return value.quantize(DETAIL, rounding=ROUND_HALF_UP)


def calculate(request: PricingRequest) -> PricingResponse:
    # Isolate precision from any caller's decimal context. Retain precision until output.
    with localcontext() as context:
        context.prec = 50
        return _calculate(request)


def _calculate(request: PricingRequest) -> PricingResponse:
    totals = dict.fromkeys(CostCategory, ZERO)
    for cost in request.costs:
        totals[cost.category] += cost.amount
    labor_total = sum((item.hours * item.hourly_rate for item in request.labor), ZERO)
    batch_total = sum(totals.values(), labor_total)
    unit_cost = batch_total / request.sellable_units
    fixed_fee = request.payment_fees.fixed_per_order / request.payment_fees.units_per_order
    rate = request.payment_fees.rate

    def price_for_margin(margin: Decimal) -> Decimal:
        return ((unit_cost + fixed_fee) / (ONE - rate - margin)).quantize(
            CENT, rounding=ROUND_CEILING
        )

    scenarios = []
    for price in request.proposed_prices:
        fee = price * rate + fixed_fee
        profit = price - fee - unit_cost
        margin = profit / price if price else None
        scenarios.append(
            PriceScenario(
                price=price,
                processing_fee_per_unit=detail(fee),
                profit_per_unit=detail(profit),
                batch_profit=detail(profit * request.sellable_units),
                margin=detail(margin) if margin is not None else None,
                markup=detail((price - unit_cost) / unit_cost) if unit_cost else None,
                below_break_even=profit < 0,
                below_target_margin=(margin is None or margin < request.target_margin.minimum),
            )
        )

    warnings = [
        Warning(
            code="UNVERIFIED_INPUTS",
            message="Costs, yield, margins, and fees are seller-supplied and unverified.",
        ),
        Warning(
            code="MARKET_NOT_EVALUATED",
            message="No local comparable products or buyer affordability evidence was evaluated.",
        ),
        Warning(
            code="QUALITY_NOT_EVALUATED",
            message="Quality requirements were not evaluated; no substitutions are recommended.",
        ),
    ]
    if not labor_total:
        warnings.append(Warning(code="NO_LABOR_COST", message="No labor compensation included."))
    if not any(
        totals[key]
        for key in (CostCategory.UTILITIES, CostCategory.EQUIPMENT, CostCategory.OVERHEAD)
    ):
        warnings.append(Warning(code="NO_OVERHEAD_COST", message="No overhead costs included."))
    if any(scenario.below_break_even for scenario in scenarios):
        warnings.append(
            Warning(
                code="UNSUSTAINABLE_PRICE", message="At least one proposed price produces a loss."
            )
        )

    return PricingResponse(
        costs=CostBreakdown(
            category_totals={key: detail(value) for key, value in totals.items()},
            labor_total=detail(labor_total),
            batch_total=detail(batch_total),
            unit_cost=detail(unit_cost),
        ),
        fixed_fee_per_unit=detail(fixed_fee),
        break_even_price=price_for_margin(ZERO),
        sustainable_price_range=PriceRange(
            minimum=price_for_margin(request.target_margin.minimum),
            maximum=price_for_margin(request.target_margin.maximum),
        ),
        scenarios=scenarios,
        warnings=warnings,
        assumptions=[
            "All monetary inputs are USD; all rates are fractions of selling price.",
            "Batch costs include consumed materials and waste; yield counts sellable units only.",
            "Labor is hours times hourly rate; do not include it again in batch costs.",
            "The fixed processing fee is shared across the supplied units per order.",
            "Fees are estimates without provider-specific rounding, taxes, or currency conversion.",
            "Batch profit assumes every sellable unit sells at the simulated price.",
            "Price bounds round up to cents; other calculated details round to six decimal places.",
            "Margin is profit after modeled fees divided by revenue; markup excludes fees.",
            "The range reflects seller margin targets, not verified fairness or an AI result.",
            "The seller retains control of final prices and quality standards.",
        ],
    )
