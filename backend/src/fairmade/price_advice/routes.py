from uuid import UUID

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.price_advice.schemas import AdviceReport, AdviceRequest
from fairmade.price_advice.service import recommend
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/products/{product_id}/pricing-recommendations",
    tags=["conditional price recommendations"],
    route_class=NoStoreRoute,
    responses={**AUTH_ERRORS, **{code: {"model": ErrorResponse} for code in (403, 404, 409)}},
)


@router.post("", response_model=AdviceReport)
def recommendations(product_id: UUID, body: AdviceRequest, db: DB, seller: VerifiedSeller):
    return recommend(db, seller.id, str(product_id), body.review_id)
