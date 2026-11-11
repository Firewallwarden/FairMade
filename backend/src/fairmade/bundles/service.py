"""Compose current public products, private preferences or private seller patterns."""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from fairmade import stock
from fairmade.auth import api_error
from fairmade.baskets.schemas import CandidateDecision
from fairmade.bundles import domain, history
from fairmade.bundles.schemas import BundleReport, BundleRequest, BundleSuggestion
from fairmade.database import utcnow
from fairmade.marketplace.repository import visible_listings
from fairmade.marketplace.schemas import CatalogDetail
from fairmade.marketplace.service import get_public
from fairmade.models import MarketplaceListing, Product
from fairmade.orders.domain import money
from fairmade.orders.schemas import CartLine, CartRequest
from fairmade.personalization import profiles
from fairmade.personalization.activity import signals
from fairmade.personalization.ranking import evaluate
from fairmade.personalization.schemas import Preferences
from fairmade.personalization.service import EMPTY_ACTIVITY
from fairmade.storefronts.repository import public_profile
from fairmade.storefronts.service import public_response

NOTICES = [
    "Suggestions pair one listed selling unit of each of two different products at one storefront.",
    "The subtotal is the sum of approved prices: no discount or guaranteed saving is established.",
    "Only your supplied candidates are considered; this is not an exhaustive marketplace search.",
    "No complementarity, ingredient compatibility, "
    "nutritional suitability or quality is certified.",
    "Mandatory quality, safety and ethical requirements remain binding; review missing evidence.",
    "Known quality concerns, insufficient stock and buyer hard constraints exclude candidates.",
    "Merchandise only: taxes, fees and travel not modeled here remain unknown.",
    "No bundle product, promotion, order, stock hold, price change or payment is created.",
    "Recheck current listing revisions and stock through cart preview before confirming purchase.",
]


@dataclass
class BundleSnapshot:
    result: BundleReport
    fingerprint: str


@dataclass
class CandidateSnapshot:
    details: dict[str, CatalogDetail]
    eligible: dict[str, domain.CandidateScore]
    decisions: list[CandidateDecision]
    stock_sources: dict[str, tuple[int, str | None, int]]


def load_candidates(
    db: Session,
    seller_id: str,
    body: BundleRequest,
    preferences: Preferences,
    activity: dict,
    *,
    seller: bool,
) -> CandidateSnapshot:
    details, eligible, decisions, stock_sources = {}, {}, [], {}
    now = utcnow()
    for item in body.candidates:
        identifier = str(item.listing_id)
        row = db.scalar(
            visible_listings()
            .join(Product, Product.id == MarketplaceListing.product_id)
            .where(MarketplaceListing.id == identifier, Product.account_id == seller_id)
        )
        if row is None:
            raise api_error(404, "NOT_FOUND", "Resource not found.")
        if row.published_revision != item.expected_listing_revision:
            raise api_error(409, "LISTING_CHANGED", "Review the current approved listing revision.")
        listing = get_public(db, identifier)
        match = evaluate(listing, preferences, activity)
        balance = stock.balance(db, row.product_id, now)
        exclusions = list(match["exclusions"])
        if balance.revision == 0:
            exclusions.append("INVENTORY_NOT_CONFIGURED")
        elif balance.selling_unit != listing.payload.product.selling_unit:
            exclusions.append("INVENTORY_UNIT_MISMATCH")
        elif balance.available < 1:
            exclusions.append("INSUFFICIENT_STOCK")
        decisions.append(
            CandidateDecision(
                listing_id=item.listing_id,
                eligible=not exclusions,
                exclusions=sorted(set(exclusions)),
                affinity_reasons=match["reasons"] if not seller else [],
            )
        )
        details[identifier] = listing
        stock_sources[identifier] = (balance.revision, balance.selling_unit, balance.available)
        if not exclusions:
            eligible[identifier] = {
                "price_minor": int(listing.payload.price.amount * 100),
                "rank": match["rank"],
            }
    return CandidateSnapshot(details, eligible, decisions, stock_sources)


def suggestions_for(
    ranked: list[domain.Pair],
    sources: CandidateSnapshot,
    budget_minor: int | None,
    limit: int,
    *,
    seller: bool,
) -> list[BundleSuggestion]:
    suggestions = []
    for pair in ranked[:limit]:
        selected = [sources.details[pair.left], sources.details[pair.right]]
        reasons = ["SAME_STOREFRONT", "CURRENT_APPROVED_PRICES", "STOCK_REPORTED_AVAILABLE"]
        if budget_minor is not None:
            reasons.append("WITHIN_EXPLICIT_TOTAL_BUDGET")
        if seller:
            reasons.append(
                "OBSERVED_SANDBOX_COPURCHASE" if pair.observed_orders else "NO_OBSERVED_COPURCHASE"
            )
        else:
            reasons += sorted(
                {
                    reason
                    for decision in sources.decisions
                    if str(decision.listing_id) in (pair.left, pair.right)
                    for reason in decision.affinity_reasons
                }
            )
        cart = (
            None
            if seller
            else CartRequest(
                items=[
                    CartLine(
                        listing_id=row.id,
                        expected_listing_revision=row.published_revision,
                        quantity=1,
                    )
                    for row in selected
                ]
            )
        )
        suggestions.append(
            BundleSuggestion(
                listings=selected,
                subtotal=money(pair.subtotal_minor),
                reasons=reasons,
                observed_copurchase_orders=pair.observed_orders if seller else None,
                cart=cart,
            )
        )
    return suggestions


def load(db: Session, account_id: str, body: BundleRequest, *, seller: bool) -> BundleSnapshot:
    storefront = public_profile(db, body.storefront_id)
    if seller and storefront.account_id != account_id:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    if not seller and storefront.account_id == account_id:
        raise api_error(409, "SELF_PURCHASE", "Choose another seller's storefront.")
    profile = None if seller else profiles.get(db, account_id)
    preferences = profile.preferences if profile else Preferences()
    ids = [str(item.listing_id) for item in body.candidates]
    activity = signals(db, account_id, ids) if profile and profile.enabled else EMPTY_ACTIVITY
    observed, start, end = history.counts(db, account_id, ids) if seller else ({}, None, None)
    candidates = load_candidates(
        db, storefront.account_id, body, preferences, activity, seller=seller
    )
    budget_minor = int(body.budget * 100) if body.budget is not None else None
    ranked, excluded_count = domain.pairs(candidates.eligible, observed, budget_minor, seller)
    suggestions = suggestions_for(ranked, candidates, budget_minor, body.limit, seller=seller)
    notices = NOTICES + (
        [
            "Seller pairs rank by recorded co-purchase orders, then subtotal and listing IDs.",
            "Co-purchase uses closed UTC dates of verified sandbox captures "
            "without refund requests; "
            "it does not establish future demand, profit or a discount budget.",
            "Co-purchase follows listing identity across revisions; "
            "historical versions may differ from current products.",
        ]
        if seller
        else [
            "Buyer pairs rank by consented affinity, then subtotal and listing IDs; "
            "they do not use other buyers' activity or seller-private sales.",
            "Per-item profile budgets remain binding; the explicit pair budget is separate.",
        ]
    )
    result = BundleReport(
        role="seller" if seller else "buyer",
        storefront_id=body.storefront_id,
        budget=money(budget_minor) if budget_minor is not None else None,
        personalized=bool(profile and profile.enabled),
        profile_revision=profile.revision if profile else 0,
        candidates=candidates.decisions,
        suggestions=suggestions,
        eligible_pairs=len(ranked),
        budget_excluded_pairs=excluded_count,
        history_start_date=start,
        history_end_date=end,
        notices=notices,
    )
    sources = {
        "result": result.model_dump(mode="json"),
        "storefront": public_response(storefront).model_dump(mode="json"),
        "profile": profile.model_dump(mode="json") if profile else None,
        "details": {
            key: value.model_dump(mode="json") for key, value in candidates.details.items()
        },
        "stock": candidates.stock_sources,
    }
    fingerprint = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    return BundleSnapshot(result, fingerprint)


def suggest(db: Session, account_id: str, body: BundleRequest, *, seller=False) -> BundleSnapshot:
    original = load(db, account_id, body, seller=seller)
    db.expire_all()
    current = load(db, account_id, body, seller=seller)
    if original.fingerprint != current.fingerprint:
        raise api_error(409, "BUNDLE_EVIDENCE_CHANGED", "Bundle evidence changed; try again.")
    return current
