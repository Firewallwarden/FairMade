"""Private buyer requests and receiving-seller review; approval alone is not completion."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount, VerifiedSeller
from fairmade.pagination import Limit, Offset
from fairmade.refunds import repository, service
from fairmade.refunds.errors import RefundError
from fairmade.refunds.schemas import (
    ApproveRequest,
    CreateRequest,
    DenyRequest,
    EmptyRequest,
    RefundResponse,
)
from fairmade.schemas import ErrorResponse, Page

ERRORS = {
    **AUTH_ERRORS,
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
buyer_router = APIRouter(tags=["buyer refund requests"], responses=ERRORS)
seller_router = APIRouter(
    tags=["seller refund decisions"],
    responses={**ERRORS, 403: {"model": ErrorResponse}},
)
BUYER_PATH = "/api/v1/orders/{order_id}/refund-request"
SELLER_PATH = "/api/v1/seller/orders/{order_id}/refund-request"


async def refund_error_handler(_request: Request, exc: RefundError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"detail": {"code": exc.code, "message": exc.message}},
        headers={"Cache-Control": "no-store"},
    )


def gateway(request: Request):
    provider = request.app.state.paypal_gateway
    if provider is None:
        raise RefundError("PAYPAL_DISABLED", "PayPal sandbox is not configured.", 503)
    return provider


@buyer_router.post(
    BUYER_PATH,
    status_code=201,
    response_model=RefundResponse,
    responses={200: {"model": RefundResponse}},
)
def create(order_id: UUID, body: CreateRequest, db: DB, buyer: CurrentAccount, response: Response):
    response.headers["Cache-Control"] = "no-store"
    result, created = service.create(db, buyer.id, str(order_id), body)
    response.status_code = 201 if created else 200
    return service.response(result)


@buyer_router.get(BUYER_PATH, response_model=RefundResponse)
def buyer_get(order_id: UUID, db: DB, buyer: CurrentAccount, response: Response):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, buyer.id, str(order_id))
    return service.response(service.get_request(db, str(order_id)))


@buyer_router.get("/api/v1/refund-requests", response_model=Page[RefundResponse])
def buyer_list(
    db: DB, buyer: CurrentAccount, response: Response, limit: Limit = 20, offset: Offset = 0
):
    response.headers["Cache-Control"] = "no-store"
    items = repository.request_page(db, buyer.id, limit, offset)
    return {"items": [service.response(item) for item in items], "limit": limit, "offset": offset}


@buyer_router.post(BUYER_PATH + "/reconcile", response_model=RefundResponse)
def buyer_reconcile(
    order_id: UUID,
    body: EmptyRequest,
    db: DB,
    buyer: CurrentAccount,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, buyer.id, str(order_id))
    return service.response(service.reconcile(db, buyer.id, str(order_id), gateway(request)))


@seller_router.get(SELLER_PATH, response_model=RefundResponse)
def seller_get(order_id: UUID, db: DB, seller: VerifiedSeller, response: Response):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, seller.id, str(order_id), seller=True)
    return service.response(service.get_request(db, str(order_id)))


@seller_router.get("/api/v1/seller/refund-requests", response_model=Page[RefundResponse])
def seller_list(
    db: DB, seller: VerifiedSeller, response: Response, limit: Limit = 20, offset: Offset = 0
):
    response.headers["Cache-Control"] = "no-store"
    items = repository.request_page(db, seller.id, limit, offset, seller=True)
    return {"items": [service.response(item) for item in items], "limit": limit, "offset": offset}


@seller_router.post(SELLER_PATH + "/deny", response_model=RefundResponse)
def deny(order_id: UUID, body: DenyRequest, db: DB, seller: VerifiedSeller, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.response(service.deny(db, seller.id, str(order_id), body))


@seller_router.post(SELLER_PATH + "/approve", response_model=RefundResponse)
def approve(
    order_id: UUID,
    body: ApproveRequest,
    db: DB,
    seller: VerifiedSeller,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, seller.id, str(order_id), seller=True)
    return service.response(service.approve(db, seller.id, str(order_id), body, gateway(request)))


@seller_router.post(SELLER_PATH + "/reconcile", response_model=RefundResponse)
def seller_reconcile(
    order_id: UUID,
    body: EmptyRequest,
    db: DB,
    seller: VerifiedSeller,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, seller.id, str(order_id), seller=True)
    return service.response(
        service.reconcile(db, seller.id, str(order_id), gateway(request), seller=True)
    )
