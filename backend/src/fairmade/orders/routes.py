"""Authenticated buyer/seller order views; no payment-completion endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount, VerifiedSeller
from fairmade.models import Order
from fairmade.orders import repository, service
from fairmade.orders.schemas import CartPreview, CartRequest, OrderResponse
from fairmade.pagination import Limit, Offset
from fairmade.schemas import ErrorResponse, Page

ERRORS = {**AUTH_ERRORS, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
router = APIRouter(prefix="/api/v1/orders", tags=["buyer orders"], responses=ERRORS)
seller_router = APIRouter(
    prefix="/api/v1/seller/orders",
    tags=["seller orders"],
    responses={**ERRORS, 403: {"model": ErrorResponse}},
)


@router.post("/preview", response_model=CartPreview, response_model_exclude_none=True)
def preview(body: CartRequest, db: DB, buyer: CurrentAccount, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.preview(db, buyer.id, body)


@router.post(
    "",
    status_code=201,
    response_model=OrderResponse,
    response_model_exclude_none=True,
    responses={200: {"model": OrderResponse}},
)
def create(
    body: CartRequest,
    db: DB,
    buyer: CurrentAccount,
    response: Response,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
):
    order, created = service.create(db, buyer.id, body, str(idempotency_key))
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "no-store"
    return service.response(order)


def _list(db, account_id, response, limit, offset, *, seller=False):
    response.headers["Cache-Control"] = "no-store"
    orders = db.scalars(
        repository.owned(db, account_id, seller=seller)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [service.response(order) for order in orders],
        "limit": limit,
        "offset": offset,
    }


@router.get("", response_model=Page[OrderResponse], response_model_exclude_none=True)
def list_orders(
    db: DB, buyer: CurrentAccount, response: Response, limit: Limit = 20, offset: Offset = 0
):
    return _list(db, buyer.id, response, limit, offset)


@router.get("/{order_id}", response_model=OrderResponse, response_model_exclude_none=True)
def get_order(order_id: UUID, db: DB, buyer: CurrentAccount, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.response(service.get_order(db, buyer.id, str(order_id)))


@router.post("/{order_id}/cancel", response_model=OrderResponse, response_model_exclude_none=True)
def cancel(order_id: UUID, db: DB, buyer: CurrentAccount, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.response(service.cancel(db, buyer.id, str(order_id)))


@seller_router.get("", response_model=Page[OrderResponse], response_model_exclude_none=True)
def list_received(
    db: DB, seller: VerifiedSeller, response: Response, limit: Limit = 20, offset: Offset = 0
):
    return _list(db, seller.id, response, limit, offset, seller=True)


@seller_router.get("/{order_id}", response_model=OrderResponse, response_model_exclude_none=True)
def get_received(order_id: UUID, db: DB, seller: VerifiedSeller, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.response(service.get_order(db, seller.id, str(order_id), seller=True))


@seller_router.post(
    "/{order_id}/cancel", response_model=OrderResponse, response_model_exclude_none=True
)
def cancel_received(order_id: UUID, db: DB, seller: VerifiedSeller, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.response(service.cancel(db, seller.id, str(order_id), seller=True))
