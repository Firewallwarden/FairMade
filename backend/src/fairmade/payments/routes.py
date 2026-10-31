"""Buyer checkout actions, seller reconciliation and safe public SDK configuration."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount, VerifiedSeller
from fairmade.payments import service
from fairmade.payments.errors import PaymentError
from fairmade.payments.schemas import CheckoutResponse, EmptyRequest, PublicConfig
from fairmade.schemas import ErrorResponse

ERRORS = {
    **AUTH_ERRORS,
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
router = APIRouter(
    prefix="/api/v1/orders/{order_id}/paypal-checkout", tags=["sandbox payments"], responses=ERRORS
)
seller_router = APIRouter(
    prefix="/api/v1/seller/orders/{order_id}/paypal-checkout",
    tags=["sandbox payment records"],
    responses={**ERRORS, 403: {"model": ErrorResponse}},
)
public_router = APIRouter(prefix="/api/v1/paypal", tags=["sandbox configuration"])


async def payment_error_handler(_request: Request, exc: PaymentError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"detail": {"code": exc.code, "message": exc.message}},
        headers={"Cache-Control": "no-store"},
    )


def gateway(request: Request):
    provider = request.app.state.paypal_gateway
    if provider is None:
        raise PaymentError("PAYPAL_DISABLED", "PayPal sandbox checkout is not configured.", 503)
    return provider


@public_router.get("/config", response_model=PublicConfig, response_model_exclude_none=True)
def config(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    provider = request.app.state.paypal_gateway
    return PublicConfig(
        enabled=provider is not None, client_id=provider.client_id if provider else None
    )


@router.post("", response_model=CheckoutResponse, response_model_exclude_none=True)
def create(
    order_id: UUID,
    body: EmptyRequest,
    db: DB,
    buyer: CurrentAccount,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, buyer.id, str(order_id))
    return service.response(service.create(db, buyer.id, str(order_id), gateway(request)))


@router.get("", response_model=CheckoutResponse, response_model_exclude_none=True)
def get_checkout(order_id: UUID, db: DB, buyer: CurrentAccount, response: Response):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, buyer.id, str(order_id))
    return service.response(service.get_checkout(db, str(order_id)))


@router.post("/capture", response_model=CheckoutResponse, response_model_exclude_none=True)
def capture(
    order_id: UUID,
    body: EmptyRequest,
    db: DB,
    buyer: CurrentAccount,
    request: Request,
    response: Response,
):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, buyer.id, str(order_id))
    return service.response(service.capture(db, buyer.id, str(order_id), gateway(request)))


@router.post("/reconcile", response_model=CheckoutResponse, response_model_exclude_none=True)
def reconcile(
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


@seller_router.get("", response_model=CheckoutResponse, response_model_exclude_none=True)
def seller_get(order_id: UUID, db: DB, seller: VerifiedSeller, response: Response):
    response.headers["Cache-Control"] = "no-store"
    service.owned_order(db, seller.id, str(order_id), seller=True)
    return service.response(service.get_checkout(db, str(order_id)))


@seller_router.post("/reconcile", response_model=CheckoutResponse, response_model_exclude_none=True)
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
