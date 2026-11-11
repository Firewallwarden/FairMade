"""Cent-safe conditional overlap, with mandatory quality and selling-basis gates first."""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from typing import NamedTuple

from fairmade.pricing.schemas import PriceRange

# Matches the existing Passport selling-price bound; advisory ranges must be publishable prices.
MAX_PUBLIC_PRICE = Decimal("1000000000")


class RangeDecision(NamedTuple):
    status: str
    quality: str
    market_range: PriceRange | None
    review_range: PriceRange | None
    reasons: list[str]


def quality_gate(evidence: dict, review: dict) -> str:
    rules = evidence["quality_lock_set"]["rules"]
    if not rules:
        return "not_configured"
    if review["quality"]["status"] == "claims_match_unverified":
        return "selected_claims_match_unverified"
    return "blocked"


def cent_range(lower: Decimal, upper: Decimal) -> PriceRange | None:
    with localcontext() as context:
        context.prec = 60
        minimum = max(lower, Decimal("0.01")).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        maximum = min(upper, MAX_PUBLIC_PRICE).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
    return PriceRange(minimum=minimum, maximum=maximum) if minimum <= maximum else None


def select_range(evidence: dict, review: dict) -> RangeDecision:
    economics = review["economics"]
    targets = PriceRange.model_validate(economics["sustainable_price_range"])
    source = evidence["pricing_analysis"]["product_snapshot"]
    current = evidence["product"]
    quality = quality_gate(evidence, review)
    market = review["market_context"]
    market_range = None
    if market["status"] == "comparable":
        bounds = market["reassessed_comparison"]["selected_price_range"]
        market_range = PriceRange(minimum=bounds["minimum"], maximum=bounds["maximum"])
    if any(source[key] != current[key] for key in ("product_type", "selling_unit")):
        return RangeDecision(
            "basis_changed", quality, market_range, None, ["PRICING_BASIS_CHANGED"]
        )
    if quality == "blocked":
        return RangeDecision(
            "quality_blocked", quality, market_range, None, ["MANDATORY_QUALITY_NOT_ESTABLISHED"]
        )
    if market_range is None:
        positive = cent_range(targets.minimum, targets.maximum)
        if positive is None:
            return RangeDecision(
                "no_cent_price", quality, None, None, ["NO_SUPPORTED_POSITIVE_CENT_IN_TARGET_RANGE"]
            )
        return RangeDecision("economics_only", quality, None, positive, ["NO_USABLE_MARKET_BASIS"])
    if market_range.maximum < targets.minimum:
        reasons = ["MARKET_REFERENCE_BELOW_SELLER_TARGET"]
        if market_range.maximum < Decimal(economics["break_even_price"]):
            reasons.append("MARKET_REFERENCE_BELOW_MODELED_BREAK_EVEN")
        return RangeDecision("target_market_gap", quality, market_range, None, reasons)
    if market_range.minimum > targets.maximum:
        return RangeDecision(
            "market_premium_gap", quality, market_range, None, ["MARKET_REFERENCE_ABOVE_TARGET"]
        )
    overlap = cent_range(
        max(targets.minimum, market_range.minimum), min(targets.maximum, market_range.maximum)
    )
    if overlap is None:
        return RangeDecision(
            "no_cent_price", quality, market_range, None, ["NO_SUPPORTED_CENT_IN_OVERLAP"]
        )
    return RangeDecision(
        "conditional_overlap", quality, market_range, overlap, ["CONDITIONAL_CONTEXT_OVERLAP"]
    )
