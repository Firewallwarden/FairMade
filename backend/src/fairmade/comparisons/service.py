"""Normalize selected quoted prices; do not establish a fair price or quality match."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from fairmade.comparisons.schemas import (
    ComparisonRequest,
    ComparisonResult,
    ComparisonRow,
    ObservationSnapshot,
    SelectedPriceRange,
)
from fairmade.comparisons.units import UNITS

COMPARISON_VERSION = "finished-product-comparison-v1"
DETAIL = Decimal("0.000001")

WARNINGS = [
    "UNVERIFIED_INPUTS",
    "QUALITY_NOT_EVALUATED",
    "LOCATION_NOT_VERIFIED",
    "TAX_SHIPPING_DISCOUNTS_NOT_NORMALIZED",
    "SELECTED_OBSERVATIONS_NOT_A_MARKET_SAMPLE",
    "PRICE_RANGE_IS_NOT_A_FAIRNESS_OR_SAVINGS_RECOMMENDATION",
]


def compare(
    request: ComparisonRequest,
    observations: list[ObservationSnapshot],
    product_type: str,
    as_of_date: date,
) -> ComparisonResult:
    # Keep conversion, division, comparison, and output rounding isolated from caller precision.
    with localcontext() as context:
        context.prec = 60
        target_family, target_factor = UNITS[request.target_quantity.unit]
        target_base = request.target_quantity.value * target_factor
        rows, included = [], []
        for observation in observations:
            data = observation.details
            age = (as_of_date - data.observed_on).days
            stale = age > request.max_age_days
            reasons = []
            if age < 0:
                reasons.append("FUTURE_OBSERVATION")
            if stale:
                reasons.append("STALE_OBSERVATION")
            if data.product_type != product_type:
                reasons.append("PRODUCT_TYPE_MISMATCH")
            source_family, source_factor = UNITS[data.quantity.unit]
            if source_family != target_family:
                reasons.append("INCOMPATIBLE_UNITS")
            normalized = None
            if source_family == target_family and data.product_type == product_type:
                source_base = data.quantity.value * source_factor
                normalized = data.price * target_base / source_base
            if not reasons:
                included.append(normalized)
            rows.append(
                ComparisonRow(
                    observation_id=observation.id,
                    details=data,
                    age_days=age,
                    stale=stale,
                    included_in_range=not reasons,
                    normalized_price=normalized.quantize(DETAIL, rounding=ROUND_HALF_UP)
                    if normalized is not None
                    else None,
                    exclusion_reasons=reasons,
                )
            )
        selected = SelectedPriceRange(
            included_count=len(included),
            excluded_count=len(rows) - len(included),
            minimum=min(included).quantize(DETAIL, rounding=ROUND_HALF_UP) if included else None,
            maximum=max(included).quantize(DETAIL, rounding=ROUND_HALF_UP) if included else None,
        )
        warnings = list(WARNINGS)
        if not included:
            warnings.append("NO_FRESH_QUANTITY_COMPARABLE_OBSERVATIONS")
        return ComparisonResult(
            target_quantity=request.target_quantity,
            max_age_days=request.max_age_days,
            as_of_date=as_of_date,
            rows=rows,
            selected_price_range=selected,
            warnings=warnings,
        )
