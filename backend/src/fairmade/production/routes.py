"""Completed production reports only; no lifecycle or automatic stock mutations."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.ownership import require_owned_product
from fairmade.pagination import Limit, Offset
from fairmade.production import repository, service
from fairmade.production.schemas import ProductionRequest, ProductionResponse, ProductionSummary
from fairmade.schemas import ErrorResponse, Page


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/products/{product_id}/production-records",
    tags=["completed production"],
    dependencies=[Depends(no_store)],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)


@router.post(
    "",
    response_model=ProductionResponse,
    status_code=201,
    responses={200: {"model": ProductionResponse, "description": "Existing exact retry"}},
)
def save(
    product_id: UUID, body: ProductionRequest, response: Response, db: DB, seller: VerifiedSeller
):
    record, created = service.save(db, seller.id, product_id, body)
    if not created:
        response.status_code = 200
    return record


@router.get("", response_model=Page[ProductionSummary])
def records(
    product_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    include_corrected: bool = False,
    limit: Limit = 20,
    offset: Offset = 0,
):
    require_owned_product(db, seller.id, product_id)
    return {
        "items": repository.page(db, str(product_id), include_corrected, limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{record_id}", response_model=ProductionResponse)
def record(product_id: UUID, record_id: UUID, db: DB, seller: VerifiedSeller):
    require_owned_product(db, seller.id, product_id)
    return service.require_record(db, str(product_id), str(record_id))
