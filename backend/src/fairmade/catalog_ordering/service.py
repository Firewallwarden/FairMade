"""Bound and rank public data before pagination; never silently order a truncated page."""

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.availability.query import public_availability, with_availability
from fairmade.availability.schemas import AvailabilityStatus
from fairmade.catalog_ordering import repository
from fairmade.catalog_ordering.domain import Candidate, Ranked, rank
from fairmade.catalog_ordering.schemas import OrderingOptions, SortMode
from fairmade.marketplace.repository import filtered_listings
from fairmade.marketplace.service import card
from fairmade.models import MarketplaceListing
from fairmade.passports.schemas import PublicQualitySummary
from fairmade.schemas import ProductType
from fairmade.unit_pricing.schemas import ReferenceUnit


def options(
    mode: SortMode, product_type: ProductType | None, reference_unit: ReferenceUnit | None
) -> OrderingOptions:
    try:
        return OrderingOptions(mode=mode, product_type=product_type, reference_unit=reference_unit)
    except ValidationError as error:
        raise RequestValidationError(
            [
                {"loc": ("query", "sort"), "msg": item["msg"], "type": item["type"]}
                for item in error.errors()
            ]
        ) from None


def ranked(candidates: list[Candidate], scope: OrderingOptions) -> Ranked:
    if len(candidates) > repository.MAX_CANDIDATES:
        error = api_error(
            409, "ORDERING_SCOPE_TOO_LARGE", "Narrow listing filters before ordering."
        )
        error.headers = {"Cache-Control": "no-store"}
        raise error
    return rank(candidates, scope)


def candidate(row) -> Candidate:
    return Candidate(
        card=card(row[0], public_availability(row)),
        quality=PublicQualitySummary.model_validate(row.ordering_quality)
        if row.ordering_quality is not None
        else None,
    )


def catalog(
    db: Session,
    scope: OrderingOptions,
    query: str | None,
    location: str | None,
    availability: AvailabilityStatus | None,
    limit: int,
    offset: int,
) -> dict:
    statement = with_availability(
        filtered_listings(
            query=query,
            product_type=scope.product_type,
            location=location,
        ),
        availability,
    )
    rows = db.execute(
        repository.with_public_quality(statement)
        .order_by(MarketplaceListing.id)
        .limit(repository.MAX_CANDIDATES + 1)
    ).all()
    candidates = [candidate(row) for row in rows]
    return catalog_page(candidates, scope, limit, offset)


def catalog_page(
    candidates: list[Candidate], scope: OrderingOptions, limit: int, offset: int
) -> dict:
    ordered = ranked(candidates, scope)
    identifiers, metadata = ordered.page(limit, offset)
    by_id = {str(item.card.id): item.card for item in candidates}
    return {
        "items": [by_id[identifier] for identifier in identifiers],
        "limit": limit,
        "offset": offset,
        "ordering": metadata,
    }
