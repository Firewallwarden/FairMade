from uuid import UUID

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse
from fairmade.supplier_recommendations.schemas import RecommendationReport, RecommendationRequest
from fairmade.supplier_recommendations.service import recommend

router = APIRouter(
    prefix="/api/v1/products/{product_id}/supplier-recommendations",
    tags=["supplier review recommendations"],
    route_class=NoStoreRoute,
    responses={**AUTH_ERRORS, **{code: {"model": ErrorResponse} for code in (403, 404, 409)}},
)


@router.post("", response_model=RecommendationReport)
def recommendations(product_id: UUID, body: RecommendationRequest, db: DB, seller: VerifiedSeller):
    return recommend(db, seller.id, str(product_id), body.supplier_report_id, body)
