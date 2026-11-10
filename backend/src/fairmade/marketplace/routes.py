"""HTTP boundaries for seller listings and anonymous marketplace browsing."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.availability.query import public_availability
from fairmade.availability.schemas import AvailabilityStatus
from fairmade.marketplace import repository, service
from fairmade.marketplace.errors import ListingError
from fairmade.marketplace.schemas import (
    CatalogCard,
    CatalogDetail,
    ListingContent,
    ListingPreview,
    ListingResponse,
    ReplaceListing,
)
from fairmade.ownership import require_owned_product
from fairmade.pagination import Limit, Offset
from fairmade.private_http import NoStoreRoute
from fairmade.publication import PublishApproval
from fairmade.schemas import ErrorResponse, Page, ProductType

router = APIRouter(
    prefix="/api/v1/products/{product_id}/listing",
    tags=["seller listings"],
    route_class=NoStoreRoute,
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
public_router = APIRouter(
    prefix="/api/v1/marketplace/listings",
    tags=["public marketplace"],
)


async def listing_error_handler(_request: Request, exc: ListingError) -> JSONResponse:
    return JSONResponse(
        status_code=404 if exc.code == "NOT_FOUND" else 409,
        content={"detail": {"code": exc.code, "message": exc.message}},
        headers={"Cache-Control": "no-store"},
    )


@router.post("", status_code=201, response_model=ListingResponse)
def create(product_id: UUID, body: ListingContent, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.create(db, product.id, body)


@router.get("", response_model=ListingResponse)
def get_listing(product_id: UUID, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.get_listing(db, product.id)


@router.put("", response_model=ListingResponse)
def replace(product_id: UUID, body: ReplaceListing, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.replace(db, product.id, body)


@router.get("/preview", response_model=ListingPreview, response_model_exclude_none=True)
def preview(product_id: UUID, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.preview(db, product.id)


@router.post("/activate", response_model=ListingResponse)
def activate(product_id: UUID, body: PublishApproval, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.activate(db, product.id, body, seller.id)


@router.post("/deactivate", status_code=204)
def deactivate(product_id: UUID, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    service.deactivate(db, product.id)
    return Response(status_code=204)


@public_router.get("", response_model=Page[CatalogCard], response_model_exclude_none=True)
def browse(
    db: DB,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    product_type: ProductType | None = None,
    location: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    availability: AvailabilityStatus | None = None,
):
    response.headers["Cache-Control"] = "no-store"
    items = repository.browse(
        db,
        query=q.strip() if q else None,
        product_type=product_type,
        location=location.strip() if location else None,
        limit=limit,
        offset=offset,
        availability=availability,
    )
    return {
        "items": [service.card(row[0], public_availability(row)) for row in items],
        "limit": limit,
        "offset": offset,
    }


@public_router.get(
    "/{listing_id}",
    response_model=CatalogDetail,
    response_model_exclude_none=True,
    responses={404: {"model": ErrorResponse}},
)
def get_public(listing_id: UUID, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.get_public(db, str(listing_id))
