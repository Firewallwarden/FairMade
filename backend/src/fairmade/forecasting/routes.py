"""Read-only private forecast; no inference or paid provider is needed."""

from uuid import UUID

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.forecasting.schemas import ForecastRequest, ForecastResponse
from fairmade.forecasting.service import forecast
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/products/{product_id}/forecasts",
    tags=["seller observed sales baseline"],
    route_class=NoStoreRoute,
    responses={**AUTH_ERRORS, **{code: {"model": ErrorResponse} for code in (403, 404, 409)}},
)


@router.post("", response_model=ForecastResponse)
def preview(product_id: UUID, body: ForecastRequest, db: DB, seller: VerifiedSeller):
    return forecast(db, seller.id, str(product_id), body)
