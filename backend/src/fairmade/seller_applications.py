"""Record intent to sell; verification and role grants are deliberately deferred."""

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount, api_error
from fairmade.models import SellerApplication
from fairmade.schemas import (
    ErrorResponse,
    SellerApplicationRequest,
    SellerApplicationResponse,
)

router = APIRouter(
    prefix="/api/v1/seller-applications",
    tags=["seller applications"],
    responses=AUTH_ERRORS,
)


@router.post(
    "",
    status_code=201,
    response_model=SellerApplicationResponse,
    responses={200: {"model": SellerApplicationResponse}, 409: {"model": ErrorResponse}},
)
def apply_to_sell(
    body: SellerApplicationRequest,
    account: CurrentAccount,
    db: DB,
    response: Response,
) -> SellerApplication:
    if "seller" in account.roles:
        raise api_error(409, "ALREADY_SELLER", "This account already has seller access.")
    # The unique account constraint and upsert also handle concurrent retries.
    inserted = db.execute(
        insert(SellerApplication)
        .values(account_id=account.id)
        .on_conflict_do_nothing(index_elements=["account_id"])
    )
    application = db.scalar(
        select(SellerApplication).where(SellerApplication.account_id == account.id)
    )
    db.commit()
    if inserted.rowcount == 0:
        response.status_code = 200
    return application


@router.get(
    "/me",
    response_model=SellerApplicationResponse,
    responses={404: {"model": ErrorResponse}},
)
def my_application(account: CurrentAccount, db: DB) -> SellerApplication:
    application = db.scalar(
        select(SellerApplication).where(SellerApplication.account_id == account.id)
    )
    if application is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return application
