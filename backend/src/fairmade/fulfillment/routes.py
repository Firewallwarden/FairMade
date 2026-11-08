"""Only the order's buyer and currently authorized seller may read private pickup data."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount, VerifiedSeller
from fairmade.fulfillment import repository, service
from fairmade.fulfillment.schemas import PickupEvent, PickupResponse, PickupUpdate
from fairmade.pagination import Limit, Offset
from fairmade.schemas import ErrorResponse, Page


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


ERRORS = {**AUTH_ERRORS, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
buyer_router = APIRouter(
    prefix="/api/v1/orders",
    tags=["private buyer pickup"],
    dependencies=[Depends(no_store)],
    responses=ERRORS,
)
seller_router = APIRouter(
    prefix="/api/v1/seller/orders",
    tags=["private seller pickup"],
    dependencies=[Depends(no_store)],
    responses={**ERRORS, 403: {"model": ErrorResponse}},
)


@buyer_router.get("/{order_id}/fulfillment", response_model=PickupResponse)
def buyer_get(order_id: UUID, db: DB, buyer: CurrentAccount):
    return service.get(db, buyer.id, str(order_id), seller=False)


@seller_router.get("/{order_id}/fulfillment", response_model=PickupResponse)
def seller_get(order_id: UUID, db: DB, seller: VerifiedSeller):
    return service.get(db, seller.id, str(order_id), seller=True)


@seller_router.put("/{order_id}/fulfillment", response_model=PickupResponse)
def seller_update(order_id: UUID, body: PickupUpdate, db: DB, seller: VerifiedSeller):
    return service.update(db, seller.id, str(order_id), body)


def history(db, account_id, order_id, limit, offset, *, seller):
    service.require_order(db, account_id, str(order_id), seller=seller)
    return {
        "items": repository.history(db, str(order_id), limit, offset),
        "limit": limit,
        "offset": offset,
    }


@buyer_router.get("/{order_id}/fulfillment/history", response_model=Page[PickupEvent])
def buyer_history(
    order_id: UUID, db: DB, buyer: CurrentAccount, limit: Limit = 20, offset: Offset = 0
):
    return history(db, buyer.id, order_id, limit, offset, seller=False)


@seller_router.get("/{order_id}/fulfillment/history", response_model=Page[PickupEvent])
def seller_history(
    order_id: UUID, db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0
):
    return history(db, seller.id, order_id, limit, offset, seller=True)
