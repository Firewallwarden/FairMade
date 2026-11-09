"""Construct a private immutable analysis without committing its caller's transaction."""

from fairmade.models import Analysis, Product
from fairmade.pricing.schemas import PricingRequest, PricingResponse
from fairmade.schemas import ProductResponse


def build_analysis(product: Product, inputs: PricingRequest, result: PricingResponse) -> Analysis:
    return Analysis(
        product_id=product.id,
        calculation_version=result.calculation_version,
        product_snapshot=ProductResponse.model_validate(product).model_dump(mode="json"),
        inputs=inputs.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )
