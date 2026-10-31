"""Private seller inventory endpoints."""

from uuid import UUID

from fastapi import APIRouter, Response

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.inventory import service
from fairmade.inventory.schemas import InventoryReplacement, InventoryResponse
from fairmade.ownership import require_owned_product
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/products/{product_id}/inventory",
    tags=["seller inventory"],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)


@router.get("", response_model=InventoryResponse)
def get_inventory(product_id: UUID, db: DB, seller: VerifiedSeller, response: Response):
    response.headers["Cache-Control"] = "no-store"
    product = require_owned_product(db, seller.id, product_id)
    return service.get_inventory(db, product.id)


@router.put("", response_model=InventoryResponse)
def replace(
    product_id: UUID, body: InventoryReplacement, db: DB, seller: VerifiedSeller, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    product = require_owned_product(db, seller.id, product_id)
    return service.replace(db, product.id, body)
