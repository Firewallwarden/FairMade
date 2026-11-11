"""Seller-owned on-demand alert report; no notification service or mutation."""

from uuid import UUID

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse
from fairmade.seller_insights.schemas import InsightReport, InsightRequest
from fairmade.seller_insights.service import report

router = APIRouter(
    prefix="/api/v1/products/{product_id}/insights",
    tags=["private seller insights"],
    route_class=NoStoreRoute,
    responses={**AUTH_ERRORS, **{status: {"model": ErrorResponse} for status in (403, 404, 409)}},
)


@router.post("", response_model=InsightReport)
def insights(product_id: UUID, body: InsightRequest, db: DB, seller: VerifiedSeller):
    return report(db, seller.id, str(product_id), body, body.analysis_id)
