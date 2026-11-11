"""General FairMade accounts and private seller production-economics APIs."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fairmade.admin_review.routes import router as admin_review_router
from fairmade.assistants.routes import router as assistant_router
from fairmade.auth import router as auth_router
from fairmade.baskets.routes import router as basket_router
from fairmade.bundles.routes import router as bundle_router
from fairmade.commerce_errors import CommerceError
from fairmade.commerce_http import commerce_error_handler
from fairmade.comparisons.routes import router as comparison_router
from fairmade.conversations.routes import router as conversation_router
from fairmade.cost_calendar.routes import router as calendar_router
from fairmade.database import database_url, make_engine
from fairmade.description_drafts.routes import router as description_router
from fairmade.discovery.routes import router as discovery_router
from fairmade.favorites.routes import router as favorites_router
from fairmade.forecasting.routes import router as forecast_router
from fairmade.fulfillment.routes import buyer_router as pickup_buyer_router
from fairmade.fulfillment.routes import seller_router as pickup_seller_router
from fairmade.inventory.routes import router as inventory_router
from fairmade.livestock.routes import router as livestock_router
from fairmade.marketplace.errors import ListingError
from fairmade.marketplace.routes import listing_error_handler
from fairmade.marketplace.routes import public_router as marketplace_public_router
from fairmade.marketplace.routes import router as marketplace_router
from fairmade.materials.routes import router as material_router
from fairmade.order_messages.routes import router as order_message_router
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
from fairmade.personalization.routes import router as personalization_router
from fairmade.photos.routes import public_router as public_photo_router
from fairmade.photos.routes import router as photo_router
from fairmade.price_advice.routes import router as price_advice_router
from fairmade.pricing.schemas import PricingRequest, PricingResponse
from fairmade.pricing.service import calculate
from fairmade.product_reviews.routes import author_router as review_author_router
from fairmade.product_reviews.routes import public_router as product_review_public_router
from fairmade.product_reviews.routes import purchase_router as review_purchase_router
from fairmade.production.routes import router as production_router
from fairmade.products import router as product_router
from fairmade.quality.routes import router as quality_router
from fairmade.receipts.routes import router as receipt_router
from fairmade.recipes.routes import router as recipe_router
from fairmade.refunds.errors import RefundError
from fairmade.refunds.routes import buyer_router as buyer_refund_router
from fairmade.refunds.routes import refund_error_handler
from fairmade.refunds.routes import seller_router as seller_refund_router
from fairmade.reviews.routes import router as review_router
from fairmade.sales.routes import cost_router as sales_cost_router
from fairmade.sales.routes import router as sales_router
from fairmade.seller_applications import router as application_router
from fairmade.seller_insights.routes import router as insight_router
from fairmade.storefronts.routes import public_router as public_storefront_router
from fairmade.storefronts.routes import router as storefront_router
from fairmade.supplier_recommendations.routes import router as recommendation_router
from fairmade.supplier_records.routes import router as supplier_record_router
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

    application = FastAPI(title="FairMade API", version="0.44.1", lifespan=lifespan)
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
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    @application.exception_handler(RequestValidationError)
    async def safe_validation(request: Request, exc: RequestValidationError):
        if (
            request.url.path.startswith("/api/v1/auth/")
            or request.url.path.endswith("/insights")
            or request.url.path.endswith("/cost-calendar")
            or request.url.path.endswith("/supplier-recommendations")
            or request.url.path.endswith("/pricing-recommendations")
            or request.url.path.startswith("/api/v1/assistants")
            or request.url.path.startswith("/api/v1/buyer/personalization")
            or request.url.path.startswith("/api/v1/buyer/baskets")
            or request.url.path.endswith("/bundles/suggest")
            or request.url.path.endswith("/forecasts")
            or request.url.path.endswith("/messages")
            or "/description-drafts" in request.url.path
            or request.url.path.startswith("/api/v1/seller/receipt-drafts")
            or request.url.path.startswith("/api/v1/marketplace/listings")
            or request.url.path.startswith("/api/v1/storefronts")
            or "/passports" in request.url.path
            or "/paypal-checkout" in request.url.path
            or "/refund-request" in request.url.path
            or "/sourcing-inputs" in request.url.path
            or "/sales-cost-basis" in request.url.path
            or request.url.path.startswith("/api/v1/seller/sales")
            or request.url.path.startswith("/api/v1/favorites")
            or request.url.path.startswith("/api/v1/seller/storefronts")
            or request.url.path.startswith("/api/v1/discovery")
            or "/photos" in request.url.path
            or "/fulfillment" in request.url.path
            or request.url.path.startswith("/api/v1/account/product-reviews")
            or request.url.path.startswith("/api/v1/admin/")
            or "/recipe" in request.url.path
            or request.url.path.startswith("/api/v1/seller/materials")
            or "/production-records" in request.url.path
            or request.url.path.startswith("/api/v1/seller/livestock")
            or (request.url.path.startswith("/api/v1/products/") and "/listing" in request.url.path)
            or request.url.path.startswith("/api/v1/seller/suppliers")
            or (
                request.url.path.startswith("/api/v1/orders/")
                and request.url.path.endswith("/review")
            )
        ):
            # Validation errors may otherwise echo the raw password or entire body.
            errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
            return JSONResponse(
                status_code=422,
                content={"detail": jsonable_encoder(errors)},
                headers={"Cache-Control": "no-store"},
            )
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
    application.include_router(insight_router)
    application.include_router(calendar_router)
    application.include_router(personalization_router)
    application.include_router(basket_router)
    application.include_router(bundle_router)
    application.include_router(forecast_router)
    application.include_router(recommendation_router)
    application.include_router(price_advice_router)
    application.include_router(description_router)
    application.include_router(receipt_router)
    application.include_router(assistant_router)
    application.include_router(conversation_router)
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
    application.include_router(order_message_router)
    application.include_router(seller_order_router)
    application.include_router(payment_router)
    application.include_router(seller_payment_router)
    application.include_router(paypal_config_router)
    application.include_router(buyer_refund_router)
    application.include_router(seller_refund_router)
    application.include_router(supplier_router)
    application.include_router(sales_cost_router)
    application.include_router(sales_router)
    application.include_router(favorites_router)
    application.include_router(storefront_router)
    application.include_router(public_storefront_router)
    application.include_router(discovery_router)
    application.include_router(photo_router)
    application.include_router(public_photo_router)
    application.include_router(pickup_buyer_router)
    application.include_router(pickup_seller_router)
    application.include_router(review_purchase_router)
    application.include_router(review_author_router)
    application.include_router(product_review_public_router)
    application.include_router(admin_review_router)
    application.include_router(recipe_router)
    application.include_router(material_router)
    application.include_router(production_router)
    application.include_router(livestock_router)
    application.include_router(supplier_record_router)
    return application


app = create_app()
