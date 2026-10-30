"""HTTP entry point for the stateless Fair Price Engine API."""

from fastapi import FastAPI

from fairmade.pricing.schemas import PricingRequest, PricingResponse
from fairmade.pricing.service import calculate

app = FastAPI(title="FairMade API", version="0.1.0")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/pricing/analyze", response_model=PricingResponse, tags=["pricing"])
def analyze_pricing(request: PricingRequest) -> PricingResponse:
    """Estimate production economics from seller inputs without saving or publishing them."""
    return calculate(request)
