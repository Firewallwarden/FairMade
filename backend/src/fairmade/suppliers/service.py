"""Pure purchase arithmetic and claim checks; never certify a substitution."""

from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext

from fairmade.quality.schemas import Rule
from fairmade.quality.service import EVALUATION_VERSION, evaluate
from fairmade.suppliers.schemas import (
    SupplierComparisonRequest,
    SupplierComparisonResult,
    SupplierComparisonRow,
    SupplierCost,
    SupplierQuoteData,
    SupplierQuoteSnapshot,
    SupplyQuantity,
)
from fairmade.units import UNITS

COMPARISON_VERSION = "supplier-comparison-v1"
DETAIL = Decimal("0.000001")
CENT = Decimal("0.01")
MAX_PACKAGES = 1_000_000


def rounded(value: Decimal, precision: Decimal = DETAIL) -> Decimal:
    return value.quantize(precision, rounding=ROUND_HALF_UP)


def purchase_cost(quote: SupplierQuoteData, required: SupplyQuantity) -> SupplierCost | None:
    """Buy whole packages, honor the bulk minimum, and charge transport once."""
    source_family, source_factor = UNITS[quote.package_quantity.unit]
    target_family, target_factor = UNITS[required.unit]
    if source_family != target_family or quote.transport_cost is None:
        return None
    # Precision covers all bounded input products, ratios and final rounding.
    with localcontext() as context:
        context.prec = 60
        usable_per_package = (
            quote.package_quantity.value * source_factor * quote.usable_fraction / target_factor
        )
        needed = int(
            (required.value / usable_per_package).to_integral_value(rounding=ROUND_CEILING)
        )
        packages = max(needed, quote.minimum_packages)
        usable = packages * usable_per_package
        merchandise = quote.package_price * packages
        total = merchandise + quote.transport_cost
        return SupplierCost(
            packages_to_buy=packages,
            merchandise_cost=rounded(merchandise, CENT),
            transport_cost=rounded(quote.transport_cost, CENT),
            purchase_cost=rounded(total, CENT),
            usable_quantity=rounded(usable),
            surplus_quantity=rounded(usable - required.value),
            cost_per_usable_unit=rounded(total / usable),
        )


def exclusion_reasons(
    quote: SupplierQuoteData,
    age: int,
    as_of_date: date,
    max_age_days: int,
    quality_status: str,
    cost: SupplierCost | None,
    required: SupplyQuantity,
) -> list[str]:
    reasons = []
    if age < 0:
        reasons.append("FUTURE_QUOTE")
    if age > max_age_days:
        reasons.append("STALE_QUOTE")
    if quote.valid_until is not None and quote.valid_until < as_of_date:
        reasons.append("EXPIRED_QUOTE")
    if quote.availability != "available":
        reasons.append(
            "UNAVAILABLE" if quote.availability == "unavailable" else "AVAILABILITY_UNKNOWN"
        )
    if quote.transport_cost is None:
        reasons.append("TRANSPORT_COST_UNKNOWN")
    if UNITS[quote.package_quantity.unit][0] != UNITS[required.unit][0]:
        reasons.append("INCOMPATIBLE_UNITS")
    if quality_status != "passed":
        reasons.append("QUALITY_" + quality_status.upper())
    if cost is not None:
        if cost.packages_to_buy > MAX_PACKAGES:
            reasons.append("PURCHASE_LIMIT_EXCEEDED")
        if quote.maximum_packages is not None and cost.packages_to_buy > quote.maximum_packages:
            reasons.append("INSUFFICIENT_AVAILABLE_PACKAGES")
    return reasons


def compare_suppliers(
    request: SupplierComparisonRequest,
    quotes: list[SupplierQuoteSnapshot],
    rules: list[Rule],
    rule_revision: int,
    as_of_date: date,
) -> SupplierComparisonResult:
    rows = []
    for snapshot in quotes:
        quote = snapshot.details
        age = (as_of_date - quote.observed_on).days
        quality = evaluate(rules, quote.claims)
        cost = purchase_cost(quote, request.required_quantity)
        reasons = exclusion_reasons(
            quote,
            age,
            as_of_date,
            request.max_age_days,
            quality.status,
            cost,
            request.required_quantity,
        )
        rows.append(
            SupplierComparisonRow(
                quote_id=snapshot.id,
                details=quote,
                age_days=age,
                quality=quality,
                cost=cost,
                eligible_for_cost_comparison=not reasons,
                exclusion_reasons=reasons,
            )
        )
    eligible = [
        row.cost for row in rows if row.eligible_for_cost_comparison and row.cost is not None
    ]
    warnings = [
        "SELLER_REPORTED_UNVERIFIED",
        "SOURCE_LOCATION_AND_AVAILABILITY_NOT_VERIFIED",
        "INPUT_REQUIREMENTS_ONLY_PRODUCT_QUALITY_NOT_EVALUATED",
        "NOT_A_SUBSTITUTION_OR_FAIRNESS_RECOMMENDATION",
        "NO_AUTOMATIC_PRICING_OR_RECIPE_CHANGES",
        "TAX_DISCOUNTS_STORAGE_AND_FINANCING_NOT_MODELED",
        "UNIT_COSTS_AND_USABLE_QUANTITIES_ROUNDED_TO_SIX_DECIMALS",
    ]
    if not eligible:
        warnings.append("NO_ELIGIBLE_QUOTES")
    if any(row.quality.status == "failed" for row in rows):
        warnings.append("SOME_QUOTES_FAIL_MANDATORY_REQUIREMENTS")
    return SupplierComparisonResult(
        as_of_date=as_of_date,
        required_quantity=request.required_quantity,
        rule_revision=rule_revision,
        quality_evaluation_version=EVALUATION_VERSION,
        rows=rows,
        eligible_count=len(eligible),
        lowest_purchase_cost=min((cost.purchase_cost for cost in eligible), default=None),
        lowest_cost_per_usable_unit=min(
            (cost.cost_per_usable_unit for cost in eligible),
            default=None,
        ),
        warnings=warnings,
    )
