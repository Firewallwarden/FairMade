"""Deterministic preference matching; affinity is never a quality/value score."""

from decimal import Decimal

from fairmade.marketplace.schemas import CatalogDetail
from fairmade.personalization.schemas import Preferences


def evaluate(listing: CatalogDetail, preferences: Preferences, activity: dict) -> dict:
    identifier = str(listing.id)
    product_type = listing.payload.product.product_type
    excluded = []
    if (
        preferences.budget_per_item is not None
        and listing.payload.price.amount > preferences.budget_per_item
    ):
        excluded.append("ABOVE_BUDGET")
    if preferences.product_types and product_type not in preferences.product_types:
        excluded.append("PRODUCT_TYPE_NOT_SELECTED")
    if (
        preferences.location
        and (listing.payload.location or "").casefold() != preferences.location.casefold()
    ):
        excluded.append("LOCATION_NOT_SELECTED")
    if listing.id in preferences.excluded_listing_ids:
        excluded.append("BUYER_EXCLUDED")
    if listing.availability.status == "unavailable":
        excluded.append("UNAVAILABLE")
    summary = listing.passport.payload.quality_summary
    if summary is not None and summary.status == "needs_attention":
        excluded.append("QUALITY_REQUIRES_ATTENTION")
    favorite = identifier in activity["favorites"]
    purchased = identifier in activity["purchases"]
    affinity = activity["types"].get(product_type, 0)
    reasons = []
    if favorite:
        reasons.append("IN_YOUR_FAVORITES")
    if purchased:
        reasons.append("PREVIOUS_VERIFIED_SANDBOX_PURCHASE")
    if affinity:
        reasons.append("CURRENT_TYPE_AFFINITY_FROM_PURCHASED_LISTINGS")
    return {
        "listing_id": identifier,
        "eligible": not excluded,
        "exclusions": excluded,
        "reasons": reasons or ["MATCHES_CURRENT_FILTERS"],
        "rank": (int(favorite), int(purchased), affinity),
        "price": Decimal(listing.payload.price.amount),
    }
