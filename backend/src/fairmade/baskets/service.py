"""Exact minimum subtotal for independent, fixed-quantity needs; no purchase effects."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from fairmade import stock
from fairmade.auth import api_error
from fairmade.baskets.schemas import (
    BasketRequest,
    BasketResponse,
    CandidateDecision,
    NeedDecision,
)
from fairmade.database import utcnow
from fairmade.marketplace.repository import visible_listings
from fairmade.marketplace.schemas import CatalogDetail
from fairmade.marketplace.service import get_public
from fairmade.models import MarketplaceListing, Product
from fairmade.orders.domain import MAX_SUBTOTAL_MINOR, money
from fairmade.orders.schemas import CartLine, CartRequest
from fairmade.orders.service import preview
from fairmade.personalization import profiles
from fairmade.personalization.activity import signals
from fairmade.personalization.ranking import evaluate
from fairmade.personalization.schemas import Preferences
from fairmade.personalization.service import EMPTY_ACTIVITY
from fairmade.storefronts.repository import public_profile
from fairmade.storefronts.service import public_response

NOTICES = [
    "Lowest merchandise subtotal among supplied acceptable alternatives for all fixed quantities.",
    "One storefront, one order and pickup; multi-seller shopping plans are a future enhancement.",
    "No quantities reduced, extra items added, discounts invented or published prices changed.",
    "Alternatives require matching product type, selling unit and declared contents; "
    "quality is not equivalent or certified.",
    "Confirmed per-item preferences remain binding; a basket budget is separate "
    "and never remembered automatically.",
    "Favorites and verified sandbox activity break equal-cost ties only, with your active consent.",
    "Merchandise only: unmodeled fees, taxes and travel are unknown. "
    "No stock, order or payment is reserved or created.",
    "Review each product's ingredients and requirements; missing quality evidence "
    "does not establish safety or suitability.",
    "Recheck the returned cart through order preview before explicit purchase confirmation; "
    "prices and stock can change.",
]


@dataclass
class BasketSnapshot:
    result: BasketResponse
    selected: list[CatalogDetail]
    fingerprint: str


def minor(amount: Decimal) -> int:
    # Request amounts are bounded decimal strings with at most two places.
    return int(amount * 100)


def compatible(listings: list[CatalogDetail]) -> None:
    if len(listings) < 2:
        return
    first = listings[0].payload
    for listing in listings:
        value = listing.payload
        if (
            value.product.product_type != first.product.product_type
            or value.product.selling_unit != first.product.selling_unit
            or value.selling_quantity is None
            or value.selling_quantity != first.selling_quantity
        ):
            raise api_error(
                409,
                "BASKET_INCOMPATIBLE_ALTERNATIVES",
                "Alternatives need identical product type, selling unit and declared contents.",
            )


def load_candidates(
    db: Session, seller_id: str, body: BasketRequest
) -> tuple[dict[str, CatalogDetail], dict[str, list[str]]]:
    details = {}
    stock_checks = {}
    now = utcnow()
    for need in body.needs:
        for item in need.alternatives:
            identifier = str(item.listing_id)
            row = db.scalar(
                visible_listings()
                .join(Product, Product.id == MarketplaceListing.product_id)
                .where(MarketplaceListing.id == identifier, Product.account_id == seller_id)
            )
            if row is None:
                # Uniform absence: never disclose private, foreign or withdrawn listing state.
                raise api_error(404, "NOT_FOUND", "Resource not found.")
            if row.published_revision != item.expected_listing_revision:
                raise api_error(
                    409, "LISTING_CHANGED", "Review the current approved listing revision."
                )
            detail = get_public(db, identifier)
            balance = stock.balance(db, row.product_id, now)
            checks = []
            if balance.revision == 0:
                checks.append("INVENTORY_NOT_CONFIGURED")
            elif balance.selling_unit != detail.payload.product.selling_unit:
                checks.append("INVENTORY_UNIT_MISMATCH")
            elif balance.available < need.quantity:
                checks.append("INSUFFICIENT_STOCK")
            details[identifier] = detail
            stock_checks[identifier] = checks
        compatible([details[str(item.listing_id)] for item in need.alternatives])

    return details, stock_checks


def choose(
    body: BasketRequest,
    details: dict[str, CatalogDetail],
    stock_checks: dict[str, list[str]],
    preferences: Preferences,
    activity: dict,
) -> tuple[list[NeedDecision], list[CatalogDetail], int]:
    # Needs have disjoint listing IDs, and each product has only one listing.
    # Their quantities are fixed, so independent line minima also minimize the total.
    decisions = []
    selected = []
    subtotal = 0
    for need in body.needs:
        candidates = []
        eligible = []
        for item in need.alternatives:
            identifier = str(item.listing_id)
            listing = details[identifier]
            match = evaluate(listing, preferences, activity)
            exclusions = sorted(set(match["exclusions"] + stock_checks[identifier]))
            candidates.append(
                CandidateDecision(
                    listing_id=item.listing_id,
                    eligible=not exclusions,
                    exclusions=exclusions,
                    affinity_reasons=[
                        reason for reason in match["reasons"] if reason != "MATCHES_CURRENT_FILTERS"
                    ],
                )
            )
            if not exclusions:
                eligible.append(
                    (
                        minor(listing.payload.price.amount) * need.quantity,
                        tuple(-value for value in match["rank"]),
                        identifier,
                    )
                )
        chosen = min(eligible) if eligible else None
        decisions.append(
            NeedDecision(
                group_id=need.group_id,
                quantity=need.quantity,
                chosen_listing_id=chosen[2] if chosen else None,
                candidates=candidates,
            )
        )
        if chosen:
            subtotal += chosen[0]
            selected.append(details[chosen[2]])

    return decisions, selected, subtotal


def load(db: Session, account_id: str, body: BasketRequest) -> BasketSnapshot:
    storefront = public_profile(db, body.storefront_id)
    if storefront.account_id == account_id:
        raise api_error(409, "SELF_PURCHASE", "Choose another seller's storefront.")
    profile = profiles.get(db, account_id)
    details, stock_checks = load_candidates(db, storefront.account_id, body)
    activity = signals(db, account_id, list(details)) if profile.enabled else EMPTY_ACTIVITY
    decisions, selected, subtotal = choose(
        body, details, stock_checks, profile.preferences, activity
    )
    complete = len(selected) == len(body.needs)
    if complete and subtotal > MAX_SUBTOTAL_MINOR:
        raise api_error(
            409, "ORDER_AMOUNT_LIMIT", "The merchandise subtotal exceeds the supported limit."
        )
    budget_minor = minor(body.budget) if body.budget is not None else None
    if not complete:
        status = "unavailable"
    elif budget_minor is not None and subtotal > budget_minor:
        status = "over_budget"
    else:
        status = "ready"
    cart = None
    priced = None
    if status == "ready":
        cart = CartRequest(
            items=[
                CartLine(
                    listing_id=item.id,
                    expected_listing_revision=item.published_revision,
                    quantity=need.quantity,
                )
                for need, item in zip(body.needs, selected, strict=True)
            ]
        )
        priced = preview(db, account_id, cart)
        if minor(priced.subtotal.amount) != subtotal:
            raise api_error(409, "BASKET_CHANGED", "Basket evidence changed; try again.")
    else:
        # An incomplete or unaffordable basket is never presented as a purchase recommendation.
        selected = []
        for decision in decisions:
            decision.chosen_listing_id = None
    result = BasketResponse(
        storefront_id=body.storefront_id,
        status=status,
        budget=money(budget_minor) if budget_minor is not None else None,
        minimum_subtotal=money(subtotal) if complete else None,
        remaining_budget=money(budget_minor - subtotal)
        if status == "ready" and budget_minor is not None
        else None,
        personalized=profile.enabled,
        profile_revision=profile.revision,
        needs=decisions,
        cart=cart,
        preview=priced,
        notices=NOTICES,
    )
    sources = {
        "storefront": public_response(storefront).model_dump(mode="json"),
        "profile": profile.model_dump(mode="json"),
        "listings": {key: value.model_dump(mode="json") for key, value in details.items()},
        "stock_checks": stock_checks,
        "activity": {
            "favorites": sorted(activity["favorites"]),
            "purchases": sorted(activity["purchases"]),
            "types": activity["types"],
        },
        "result": result.model_dump(mode="json"),
    }
    fingerprint = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    return BasketSnapshot(result, selected, fingerprint)


def optimize(db: Session, account_id: str, body: BasketRequest) -> BasketSnapshot:
    original = load(db, account_id, body)
    db.expire_all()
    current = load(db, account_id, body)
    if current.fingerprint != original.fingerprint:
        raise api_error(409, "BASKET_CHANGED", "Basket evidence or preferences changed; try again.")
    return current
