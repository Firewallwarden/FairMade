"""Public suggestions and private profile evidence, reloaded for every assistant turn."""

from decimal import ROUND_FLOOR, localcontext

from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.availability.query import public_availability, with_availability
from fairmade.marketplace import repository as catalog
from fairmade.marketplace.service import get_public
from fairmade.models import MarketplaceListing
from fairmade.personalization import profiles
from fairmade.personalization.activity import signals
from fairmade.personalization.ranking import evaluate
from fairmade.personalization.schemas import Suggest, Suggestion, Suggestions

NOTICES = [
    "Affinity uses favorites and recent sandbox purchases, without inferring sensitive traits.",
    "Budgets apply per listed selling unit, excluding any unmodeled checkout charges.",
    "Activity rank does not establish quality, equivalence, fairness or best overall value.",
    "Quality claims remain unverified; activity cannot establish required safety evidence.",
    "Availability is seller-reported and rechecked at checkout; suggestions reserve no stock.",
]
EMPTY_ACTIVITY = {"favorites": set(), "purchases": set(), "types": {}}


def suggest(db: Session, account_id: str, body: Suggest) -> Suggestions:
    profile = profiles.get(db, account_id)
    preferences = profile.preferences.model_copy(deep=True)
    for key in ("budget_per_item", "product_types", "location"):
        value = getattr(body, key)
        if value is not None:
            setattr(preferences, key, value)
    # Read only current approved catalog data. Bound the complete matching set;
    # do not silently rank a truncated latest-first subset.
    statement = catalog.visible_listings().where(
        MarketplaceListing.approved_by_account_id != account_id
    )
    if preferences.product_types:
        statement = statement.where(MarketplaceListing.product_type.in_(preferences.product_types))
    if preferences.location:
        statement = statement.where(
            MarketplaceListing.location_key == preferences.location.casefold()
        )
    if preferences.excluded_listing_ids:
        statement = statement.where(
            MarketplaceListing.id.not_in([str(value) for value in preferences.excluded_listing_ids])
        )
    if preferences.budget_per_item is not None:
        with localcontext() as context:
            context.prec = 40
            minor_limit = int(
                (preferences.budget_per_item * 100).to_integral_value(rounding=ROUND_FLOOR)
            )
        statement = statement.where(MarketplaceListing.price_minor <= minor_limit)
    rows = db.execute(
        with_availability(statement, None if body.include_unknown_availability else "available")
        .order_by(MarketplaceListing.id)
        .limit(101)
    ).all()
    if len(rows) > 100:
        raise api_error(
            409, "PERSONALIZATION_SCOPE_TOO_LARGE", "Narrow the catalog using location."
        )
    candidates = [
        row
        for row in rows
        if row[0].approved_by_account_id != account_id
        and public_availability(row).status != "unavailable"
    ]
    ids = [row[0].id for row in candidates]
    activity = signals(db, account_id, ids) if profile.enabled else EMPTY_ACTIVITY
    ranked = []
    for row in candidates:
        listing = get_public(db, row[0].id)
        match = evaluate(listing, preferences, activity)
        if match["eligible"]:
            ranked.append((match["rank"], str(listing.id), listing, match["reasons"]))
    # Stable ID ties intentionally avoid a price/quality/value ranking across
    # incompatible selling units. Hard constraints were evaluated first.
    ranked.sort(key=lambda item: (tuple(-value for value in item[0]), item[1]))
    db.expire_all()
    if profile.enabled and signals(db, account_id, ids) != activity:
        raise api_error(409, "PERSONALIZATION_CHANGED", "Shopping activity changed; try again.")
    for item in ranked[:4]:
        if get_public(db, item[1]) != item[2]:
            raise api_error(
                409, "PERSONALIZATION_CHANGED", "A suggested listing changed; try again."
            )
    if profiles.get(db, account_id) != profile:
        raise api_error(409, "PERSONALIZATION_CHANGED", "Shopping preferences changed; try again.")
    return Suggestions(
        items=[Suggestion(listing=item[2], reasons=item[3]) for item in ranked[:4]],
        personalized=profile.enabled,
        profile_revision=profile.revision,
        effective_preferences=preferences,
        notices=NOTICES,
    )


def buyer_profile_data(db: Session, account_id: str, listings: list) -> dict | None:
    profile = profiles.get(db, account_id)
    if not profile.enabled:
        return None
    ids = [str(listing.id) for listing in listings]
    activity = signals(db, account_id, ids)
    matches = [evaluate(listing, profile.preferences, activity) for listing in listings]
    return {
        "profile_revision": profile.revision,
        "preferences": profile.preferences.model_dump(mode="json"),
        "matches": [
            {key: value for key, value in match.items() if key not in ("rank", "price")}
            for match in matches
        ],
        "policy": NOTICES,
    }
