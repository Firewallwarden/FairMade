from uuid import UUID

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.cost_calendar.schemas import CalendarOptions, CostCalendar
from fairmade.cost_calendar.service import report
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/products/{product_id}/cost-calendar",
    tags=["saved cost calendar"],
    route_class=NoStoreRoute,
    responses={**AUTH_ERRORS, **{code: {"model": ErrorResponse} for code in (403, 404, 409)}},
)


@router.post("", response_model=CostCalendar)
def calendar(product_id: UUID, body: CalendarOptions, db: DB, seller: VerifiedSeller):
    return report(db, seller.id, str(product_id), body)
