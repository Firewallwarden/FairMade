"""Local seller API and the backward-compatible stateless pricing endpoint."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fairmade.auth import router as auth_router
from fairmade.database import database_url, make_engine
from fairmade.pricing.schemas import PricingRequest, PricingResponse
from fairmade.pricing.service import calculate
from fairmade.products import router as product_router


def create_app(db_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.engine = make_engine(db_url or database_url())
        try:
            yield
        finally:
            application.state.engine.dispose()

    application = FastAPI(title="FairMade API", version="0.2.0", lifespan=lifespan)
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
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @application.exception_handler(RequestValidationError)
    async def safe_validation(request: Request, exc: RequestValidationError):
        if request.url.path.startswith("/api/v1/auth/"):
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
    application.include_router(product_router)
    return application


app = create_app()
