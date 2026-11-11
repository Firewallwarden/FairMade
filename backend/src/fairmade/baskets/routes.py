"""Private planning only; purchase remains a separate confirmed order workflow."""

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount
from fairmade.baskets.schemas import BasketRequest, BasketResponse
from fairmade.baskets.service import optimize
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/buyer/baskets",
    tags=["buyer basket planning"],
    route_class=NoStoreRoute,
    responses={**AUTH_ERRORS, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)


@router.post("/optimize", response_model=BasketResponse)
def plan(body: BasketRequest, db: DB, account: CurrentAccount):
    return optimize(db, account.id, body).result
