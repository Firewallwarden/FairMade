"""Exact-radius filtering and deterministic nearest-first pagination of bounded candidates."""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.availability.query import public_availability
from fairmade.discovery import repository
from fairmade.discovery.schemas import AreaSearch, ListingSearch, NearbyListing, NearbyStorefront
from fairmade.geography import ApproximateArea, distance_km
from fairmade.marketplace.service import card
from fairmade.models import Storefront
from fairmade.storefronts.service import public_response

NOTICES = [
    "Distances are estimates between the search origin and seller-chosen approximate area points.",
    "Area points are public and unverified; they are not pickup addresses or travel distances.",
    "Only currently published storefronts with approved area points appear in nearby searches.",
    "Listings keep their approved prices and disclosures. Search does not reserve stock.",
]


def check_size(rows) -> None:
    if len(rows) > repository.MAX_CANDIDATES:
        error = api_error(
            409,
            "SEARCH_TOO_BROAD",
            "Too many area candidates; narrow the radius or text/type filters.",
        )
        error.headers = {"Cache-Control": "no-store"}
        raise error


def area_distance(body: AreaSearch, profile: Storefront) -> tuple[ApproximateArea, float]:
    area = ApproximateArea.model_validate(profile.public_payload["approximate_area"])
    return area, distance_km(body.origin, float(area.latitude), float(area.longitude))


def display_distance(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def page(body: AreaSearch, ranked: list) -> dict:
    ranked.sort(key=lambda item: (item[0], item[1]))
    return {
        "items": [item[2] for item in ranked[body.offset : body.offset + body.limit]],
        "limit": body.limit,
        "offset": body.offset,
        "notices": NOTICES,
    }


def storefronts(db: Session, body: AreaSearch) -> dict:
    rows = repository.storefront_candidates(db, body)
    check_size(rows)
    ranked = []
    for profile in rows:
        _, distance = area_distance(body, profile)
        if distance <= float(body.radius_km) + 1e-9:
            ranked.append(
                (
                    distance,
                    profile.id,
                    NearbyStorefront(
                        storefront=public_response(profile),
                        estimated_distance_km=display_distance(distance),
                    ),
                )
            )
    return page(body, ranked)


def listings(db: Session, body: ListingSearch) -> dict:
    rows = repository.listing_candidates(db, body)
    check_size(rows)
    ranked = []
    for row in rows:
        listing, profile = row[0], row[1]
        area, distance = area_distance(body, profile)
        if distance <= float(body.radius_km) + 1e-9:
            ranked.append(
                (
                    distance,
                    listing.id,
                    NearbyListing(
                        listing=card(listing, public_availability(row)),
                        storefront_id=profile.id,
                        approximate_area=area,
                        estimated_distance_km=display_distance(distance),
                    ),
                )
            )
    return page(body, ranked)
