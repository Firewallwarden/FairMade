"""General FairMade accounts and private seller production-economics APIs."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fairmade.auth import router as auth_router
from fairmade.commerce_errors import CommerceError
from fairmade.commerce_http import commerce_error_handler
from fairmade.comparisons.routes import router as comparison_router
from fairmade.database import database_url, make_engine
from fairmade.inventory.routes import router as inventory_router
from fairmade.marketplace.errors import ListingError
from fairmade.marketplace.routes import listing_error_handler
from fairmade.marketplace.routes import public_router as marketplace_public_router
from fairmade.marketplace.routes import router as marketplace_router
from fairmade.orders.routes import router as order_router
from fairmade.orders.routes import seller_router as seller_order_router
from fairmade.passports.errors import PassportError
from fairmade.passports.routes import (
    passport_error_handler,
)
from fairmade.passports.routes import (
    public_router as public_passport_router,
)
from fairmade.passports.routes import (
    router as passport_router,
)
from fairmade.payments.errors import PaymentError
from fairmade.payments.gateway import Gateway, configured_gateway
from fairmade.payments.routes import payment_error_handler
from fairmade.payments.routes import public_router as paypal_config_router
from fairmade.payments.routes import router as payment_router
from fairmade.payments.routes import seller_router as seller_payment_router
from fairmade.pricing.schemas import PricingRequest, PricingResponse
from fairmade.pricing.service import calculate
from fairmade.products import router as product_router
from fairmade.quality.routes import router as quality_router
from fairmade.refunds.errors import RefundError
from fairmade.refunds.routes import buyer_router as buyer_refund_router
from fairmade.refunds.routes import refund_error_handler
from fairmade.refunds.routes import seller_router as seller_refund_router
from fairmade.reviews.routes import router as review_router
from fairmade.sales.routes import cost_router as sales_cost_router
from fairmade.sales.routes import router as sales_router
from fairmade.seller_applications import router as application_router
from fairmade.suppliers.routes import router as supplier_router


def create_app(db_url: str | None = None, *, paypal_gateway: Gateway | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        with configured_gateway(paypal_gateway) as gateway:
            application.state.paypal_gateway = gateway
            application.state.engine = make_engine(db_url or database_url())
            try:
                yield
            finally:
                application.state.engine.dispose()

    application = FastAPI(title="FairMade API", version="0.13.0", lifespan=lifespan)
    application.add_exception_handler(RefundError, refund_error_handler)
    application.add_exception_handler(PaymentError, payment_error_handler)
    application.add_exception_handler(CommerceError, commerce_error_handler)
    application.add_exception_handler(PassportError, passport_error_handler)
    application.add_exception_handler(ListingError, listing_error_handler)
    origins = [
        value.strip()
        for value in os.environ.get("FAIRMADE_CORS_ORIGINS", "").split(",")
        if value.strip()
    ]
    if "*" in origins:
        raise ValueError("Configure explicit CORS origins, not a wildcard")
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST", "PATCH", "PUT"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    @application.exception_handler(RequestValidationError)
    async def safe_validation(request: Request, exc: RequestValidationError):
        if (
            request.url.path.startswith("/api/v1/auth/")
            or "/paypal-checkout" in request.url.path
            or "/refund-request" in request.url.path
            or "/sourcing-inputs" in request.url.path
            or "/sales-cost-basis" in request.url.path
            or request.url.path.startswith("/api/v1/seller/sales")
        ):
            # Validation errors may otherwise echo the raw password or entire body.
            errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
            return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})
        return await request_validation_exception_handler(request, exc)

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post(
        "/api/v1/pricing/analyze",
        response_model=PricingResponse,
        tags=["pricing"],
    )
    def analyze_pricing(request: PricingRequest) -> PricingResponse:
        """Estimate economics without saving or publishing seller inputs."""
        return calculate(request)

    application.include_router(auth_router)
    application.include_router(application_router)
    application.include_router(product_router)
    application.include_router(quality_router)
    application.include_router(comparison_router)
    application.include_router(review_router)
    application.include_router(passport_router)
    application.include_router(public_passport_router)
    application.include_router(marketplace_router)
    application.include_router(marketplace_public_router)
    application.include_router(inventory_router)
    application.include_router(order_router)
    application.include_router(seller_order_router)
    application.include_router(payment_router)
    application.include_router(seller_payment_router)
    application.include_router(paypal_config_router)
    application.include_router(buyer_refund_router)
    application.include_router(seller_refund_router)
    application.include_router(supplier_router)
    application.include_router(sales_cost_router)
    application.include_router(sales_router)
    return application


app = create_app()
