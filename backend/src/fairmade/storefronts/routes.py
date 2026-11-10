"""Private seller editing and anonymous, allowlisted storefront discovery."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.availability.query import public_availability
from fairmade.availability.schemas import AvailabilityStatus
from fairmade.marketplace.schemas import CatalogCard
from fairmade.marketplace.service import card
from fairmade.models import Storefront
from fairmade.pagination import Limit, Offset
from fairmade.publication import PublishApproval
from fairmade.schemas import ErrorResponse, Page
from fairmade.storefronts import repository, service
from fairmade.storefronts.schemas import (
    PublicStorefront,
    ReplaceStorefront,
    StorefrontContent,
    StorefrontDraft,
    StorefrontPreview,
)


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/seller/storefronts",
    tags=["private seller storefronts"],
    dependencies=[Depends(no_store)],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
public_router = APIRouter(
    prefix="/api/v1/storefronts",
    tags=["public storefronts"],
    dependencies=[Depends(no_store)],
    responses={404: {"model": ErrorResponse}},
)


@router.post("", response_model=StorefrontDraft, status_code=201)
def create(body: StorefrontContent, db: DB, seller: VerifiedSeller) -> Storefront:
    return repository.create(db, seller.id, body)


@router.get("", response_model=Page[StorefrontDraft])
def own_storefronts(
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    return {
        "items": repository.own_page(db, seller.id, limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{storefront_id}", response_model=StorefrontDraft)
def get(storefront_id: UUID, db: DB, seller: VerifiedSeller) -> Storefront:
    return repository.owned(db, seller.id, storefront_id)


@router.put("/{storefront_id}", response_model=StorefrontDraft)
def replace(
    storefront_id: UUID,
    body: ReplaceStorefront,
    db: DB,
    seller: VerifiedSeller,
) -> Storefront:
    return service.replace(db, seller.id, storefront_id, body)


@router.get(
    "/{storefront_id}/preview", response_model=StorefrontPreview, response_model_exclude_none=True
)
def preview(storefront_id: UUID, db: DB, seller: VerifiedSeller) -> StorefrontPreview:
    return service.preview(repository.owned(db, seller.id, storefront_id))


@router.post(
    "/{storefront_id}/publish", response_model=PublicStorefront, response_model_exclude_none=True
)
def publish(
    storefront_id: UUID,
    body: PublishApproval,
    db: DB,
    seller: VerifiedSeller,
) -> PublicStorefront:
    return service.publish(db, seller.id, storefront_id, body)


@router.post("/{storefront_id}/withdraw", status_code=204)
def withdraw(storefront_id: UUID, db: DB, seller: VerifiedSeller) -> Response:
    service.withdraw(db, seller.id, storefront_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@public_router.get("", response_model=Page[PublicStorefront], response_model_exclude_none=True)
def browse(
    db: DB,
    limit: Limit = 20,
    offset: Offset = 0,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    location: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> dict:
    rows = repository.browse(
        db,
        q.strip() if q else None,
        location.strip() if location else None,
        limit,
        offset,
    )
    return {
        "items": [service.public_response(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@public_router.get(
    "/{storefront_id}", response_model=PublicStorefront, response_model_exclude_none=True
)
def public_profile(storefront_id: UUID, db: DB) -> PublicStorefront:
    return service.public_response(repository.public_profile(db, storefront_id))


@public_router.get(
    "/{storefront_id}/listings", response_model=Page[CatalogCard], response_model_exclude_none=True
)
def listings(
    storefront_id: UUID,
    db: DB,
    limit: Limit = 20,
    offset: Offset = 0,
    availability: AvailabilityStatus | None = None,
) -> dict:
    repository.public_profile(db, storefront_id)
    rows = repository.listings(db, storefront_id, limit, offset, availability)
    return {
        "items": [card(row[0], public_availability(row)) for row in rows],
        "limit": limit,
        "offset": offset,
    }
