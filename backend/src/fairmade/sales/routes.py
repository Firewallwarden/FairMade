"""Verified sellers configure private cost estimates and read their own sales."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller, api_error
from fairmade.database import utcnow
from fairmade.ownership import require_owned_product
from fairmade.pagination import Limit, Offset
from fairmade.sales import cost_basis, repository, service
from fairmade.sales.schemas import (
    CostBasisResponse,
    SalesOrderResponse,
    SalesSummary,
    SelectCostBasis,
)
from fairmade.schemas import ErrorResponse, Page

ERRORS = {
    **AUTH_ERRORS,
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
}
cost_router = APIRouter(
    prefix="/api/v1/products/{product_id}/sales-cost-basis",
    tags=["private sales cost basis"],
    responses=ERRORS,
)
router = APIRouter(prefix="/api/v1/seller/sales", tags=["seller sales reporting"], responses=ERRORS)


@cost_router.get("", response_model=CostBasisResponse)
def get_cost_basis(product_id: UUID, db: DB, seller: VerifiedSeller) -> CostBasisResponse:
    product = require_owned_product(db, seller.id, product_id)
    return cost_basis.current(db, product.id)


@cost_router.put("", response_model=CostBasisResponse)
def select_cost_basis(
    product_id: UUID,
    body: SelectCostBasis,
    db: DB,
    seller: VerifiedSeller,
) -> CostBasisResponse:
    product = require_owned_product(db, seller.id, product_id)
    return cost_basis.select_basis(db, product, body)


def validate_period(start_date: date, end_date: date) -> None:
    days = (end_date - start_date).days
    if not 1 <= days <= 366:
        raise api_error(422, "INVALID_PERIOD", "Use an exclusive end date, 1-366 days after start.")


@router.get("", response_model=SalesSummary)
def sales_summary(
    start_date: date,
    end_date: date,
    db: DB,
    seller: VerifiedSeller,
) -> SalesSummary:
    validate_period(start_date, end_date)
    records = repository.summary_records(db, seller.id, start_date, end_date)
    if len(records) > repository.MAX_SUMMARY_ORDERS:
        raise api_error(
            409, "REPORT_TOO_LARGE", "Narrow the period to at most 1000 captured sales."
        )
    return service.summarize(records, start_date, end_date, utcnow())


@router.get("/orders", response_model=Page[SalesOrderResponse])
def sales_orders(
    start_date: date,
    end_date: date,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    validate_period(start_date, end_date)
    records = repository.page_records(db, seller.id, start_date, end_date, limit, offset)
    return {
        "items": [service.order_result(record) for record in records],
        "limit": limit,
        "offset": offset,
    }
