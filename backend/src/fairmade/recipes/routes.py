"""Private product recipe management and bounded immutable costing history."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.ownership import require_owned_product
from fairmade.pagination import Limit, Offset
from fairmade.recipes import repository, service
from fairmade.recipes.schemas import (
    CostingRequest,
    CostingResponse,
    CostingSummary,
    RecipeCreate,
    RecipeReplacement,
    RecipeResponse,
)
from fairmade.schemas import ErrorResponse, Page


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/products/{product_id}/recipe",
    tags=["recipes"],
    dependencies=[Depends(no_store)],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)


@router.post("", response_model=RecipeResponse, status_code=201)
def create(product_id: UUID, body: RecipeCreate, db: DB, seller: VerifiedSeller):
    return service.create(db, seller.id, product_id, body)


@router.get("", response_model=RecipeResponse)
def get(product_id: UUID, db: DB, seller: VerifiedSeller):
    require_owned_product(db, seller.id, product_id)
    return service.require_recipe(db, str(product_id))


@router.put("", response_model=RecipeResponse)
def replace(product_id: UUID, body: RecipeReplacement, db: DB, seller: VerifiedSeller):
    return service.replace(db, seller.id, product_id, body)


@router.post(
    "/costings",
    response_model=CostingResponse,
    status_code=201,
    responses={200: {"model": CostingResponse, "description": "Existing exact retry"}},
)
def save_costing(
    product_id: UUID, body: CostingRequest, response: Response, db: DB, seller: VerifiedSeller
):
    record, created = service.save_costing(db, seller.id, product_id, body)
    if not created:
        response.status_code = 200
    return record


@router.get("/costings", response_model=Page[CostingSummary])
def costings(
    product_id: UUID, db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0
):
    require_owned_product(db, seller.id, product_id)
    return {
        "items": repository.page(db, str(product_id), limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/costings/{costing_id}", response_model=CostingResponse)
def costing(product_id: UUID, costing_id: UUID, db: DB, seller: VerifiedSeller):
    require_owned_product(db, seller.id, product_id)
    record = repository.costing(db, str(product_id), str(costing_id))
    if record is None:
        raise service.error(404, "NOT_FOUND", "Resource not found.")
    return record
