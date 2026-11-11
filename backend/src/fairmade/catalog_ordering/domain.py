"""Stable decimal ordering over the complete bounded public candidate set."""

from dataclasses import dataclass

from fairmade.catalog_ordering.schemas import OrderingMetadata, OrderingOptions, OrderingSignal
from fairmade.marketplace.schemas import CatalogCard
from fairmade.passports.schemas import PublicQualitySummary

NOTICES = [
    "Ordering uses approved public disclosures; matching claims are unverified, not certification.",
    "Quality ordering groups unverified matching claims, unknown evidence and disclosed concerns.",
    "Listed-price ordering compares selling-unit prices, not equivalent sizes or overall value.",
    "Unit-price ordering uses published six-place display prices within the requested type/unit.",
    "Value ordering prioritizes disclosed quality-check status, availability, then unit price.",
    "Unknown quality is not a passing safety check or evidence of equal ingredients or grade.",
    "Not-compared results follow ordered results by publication recency, without a price ranking.",
    "A value concern or unavailable item is not an acceptable saving or purchase recommendation.",
    "This is an explicit ordering policy, not an objective fairness or universal value score.",
    "Prices, disclosures and stock are unchanged; checkout must recheck current availability.",
]


@dataclass(frozen=True)
class Candidate:
    card: CatalogCard
    quality: PublicQualitySummary | None


@dataclass
class Ranked:
    options: OrderingOptions
    identifiers: list[str]
    signals: dict[str, OrderingSignal]
    compared_count: int

    def page(self, limit: int, offset: int) -> tuple[list[str], OrderingMetadata]:
        selected = self.identifiers[offset : offset + limit]
        notices = list(NOTICES)
        if not self.compared_count and self.identifiers:
            notices.append(
                "No items can be compared on this basis; displayed results are not ranked by value."
            )
        return selected, OrderingMetadata(
            mode=self.options.mode,
            product_type=self.options.product_type,
            reference_unit=self.options.reference_unit,
            candidate_count=len(self.identifiers),
            compared_count=self.compared_count,
            not_compared_count=len(self.identifiers) - self.compared_count,
            items=[self.signals[identifier] for identifier in selected],
            notices=notices,
        )


def quality_status(candidate: Candidate) -> str:
    return candidate.quality.status if candidate.quality is not None else "undisclosed"


def quality_tier(candidate: Candidate) -> int:
    status = quality_status(candidate)
    if status == "claims_match_unverified":
        return 0
    return 2 if status == "needs_attention" else 1


def exclusions(candidate: Candidate, options: OrderingOptions) -> list[str]:
    if options.mode not in ("unit_price", "value"):
        return []
    card = candidate.card
    unit = card.payload.unit_price
    reasons = []
    if card.payload.product.product_type != options.product_type:
        reasons.append("PRODUCT_TYPE_MISMATCH")
    if unit is None:
        reasons.append("UNIT_PRICE_MISSING")
    elif unit.reference_unit != options.reference_unit:
        reasons.append("INCOMPATIBLE_REFERENCE_UNIT")
    elif unit.status != "calculated" or unit.amount is None:
        reasons.append("UNIT_PRICE_BELOW_DISPLAY_PRECISION")
    if options.mode == "value":
        if quality_status(candidate) == "needs_attention":
            reasons.append("QUALITY_REQUIRES_ATTENTION")
        if card.availability.status == "unavailable":
            reasons.append("UNAVAILABLE")
    return reasons


def ordering_key(candidate: Candidate, options: OrderingOptions):
    mode = options.mode
    if mode == "price_asc":
        return candidate.card.payload.price.amount
    if mode == "price_desc":
        return -candidate.card.payload.price.amount
    if mode == "quality":
        return quality_tier(candidate)
    if mode == "unit_price":
        return candidate.card.payload.unit_price.amount
    if mode == "value":
        return (
            quality_tier(candidate),
            0 if candidate.card.availability.status == "available" else 1,
            candidate.card.payload.unit_price.amount,
        )
    return 0  # Stable pre-sort already established newest first and deterministic ID ties.


def rank(candidates: list[Candidate], options: OrderingOptions) -> Ranked:
    recent = sorted(
        candidates, key=lambda item: (item.card.published_at, str(item.card.id)), reverse=True
    )
    ordered, unknown = [], []
    signals = {}
    for candidate in recent:
        reasons = exclusions(candidate, options)
        identifier = str(candidate.card.id)
        signals[identifier] = OrderingSignal(
            listing_id=candidate.card.id,
            quality_status=quality_status(candidate),
            comparison_status="not_compared" if reasons else "ordered",
            reasons=reasons,
        )
        (unknown if reasons else ordered).append(candidate)
    ordered.sort(key=lambda item: ordering_key(item, options))
    return Ranked(
        options=options,
        identifiers=[str(item.card.id) for item in ordered + unknown],
        signals=signals,
        compared_count=len(ordered),
    )
