"""Refresh owned saved-review evidence without modifying the review or any price."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.evidence import today
from fairmade.models import SellerPricingReview
from fairmade.ownership import require_owned_product
from fairmade.price_advice.domain import select_range
from fairmade.price_advice.schemas import AdviceReport, MarketSource
from fairmade.pricing.schemas import PriceRange
from fairmade.reviews.evidence import selected_evidence
from fairmade.reviews.schemas import ReviewRequest
from fairmade.reviews.service import REVIEW_VERSION, build_review

NOTICES = [
    "Conditional price range for seller review, "
    "not an objective fairness verdict or a chosen price.",
    "The saved review pins its production analysis and selected observations/evaluations; "
    "current requirements and quote freshness are reassessed without changing history.",
    "Cost assumptions, compensation, overhead, fees and margins are seller-reported; "
    "analysis save time does not establish current actual costs or verified profit.",
    "Market context describes selected reported observations with an explicit seller-declared unit "
    "mapping, not verified locality, equivalent ingredients/quality "
    "or representative market demand.",
    "An overlap is conditional on those limitations; "
    "it does not justify relaxing any Quality Lock.",
    "No overlap leaves the recommendation empty; do not silently cut compensation, "
    "quality or margin targets, or raise prices to the highest observed quote.",
    "No mandatory requirements configured is not a quality assurance. Matching selected claims "
    "remain unverified; failed, unknown or outdated selected checks block a recommendation.",
    "No range is automatically published, charged or written to a product, recipe or inventory.",
    "Recommended ranges use positive whole cents within existing publication price bounds.",
]


def load(db: Session, account_id: str, product_id: str, review_id: UUID) -> AdviceReport:
    product = require_owned_product(db, account_id, product_id)
    saved = db.scalar(
        select(SellerPricingReview).where(
            SellerPricingReview.id == str(review_id), SellerPricingReview.product_id == product.id
        )
    )
    if saved is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    if saved.review_version != REVIEW_VERSION:
        raise api_error(409, "UNSUPPORTED_EVIDENCE_VERSION", "Unsupported review version.")
    request = ReviewRequest.model_validate(saved.request_snapshot)
    evidence = selected_evidence(db, product, request)
    as_of = today()
    refreshed = build_review(request, evidence, as_of)
    status, quality, market_range, selected_range, reasons = select_range(evidence, refreshed)
    comparison = refreshed["market_context"]["reassessed_comparison"]
    sources = []
    for row in comparison["rows"] if comparison else []:
        data = row["details"]
        sources.append(
            MarketSource(
                observation_id=row["observation_id"],
                label=data["label"],
                location=data["location"],
                observed_on=data["observed_on"],
                source=data["source"],
                included=row["included_in_range"],
                normalized_price=row["normalized_price"],
                exclusions=row["exclusion_reasons"],
            )
        )
    analysis = evidence["pricing_analysis"]
    cost_warnings = [warning["code"] for warning in refreshed["economics"]["warnings"]]
    return AdviceReport(
        product_id=product.id,
        review_id=saved.id,
        pricing_analysis_id=request.pricing_analysis_id,
        analysis_saved_on=analysis["created_at"][:10],
        as_of_date=as_of,
        analysis_selling_unit=analysis["product_snapshot"]["selling_unit"],
        current_selling_unit=product.selling_unit,
        status=status,
        quality_status=quality,
        current_rule_revision=evidence["quality_lock_set"]["revision"],
        market_status=refreshed["market_context"]["status"],
        unit_cost=refreshed["economics"]["costs"]["unit_cost"],
        break_even_price=refreshed["economics"]["break_even_price"],
        seller_target_range=PriceRange.model_validate(
            refreshed["economics"]["sustainable_price_range"]
        ),
        selected_market_range=market_range,
        recommended_review_range=selected_range,
        production_unit_quantity=request.production_unit_quantity,
        market_reference_quantity=comparison["target_quantity"] if comparison else None,
        selected_quality_evaluation_ids=request.quality_evaluation_ids,
        market_sources=sources,
        reasons=reasons,
        notices=list(dict.fromkeys(NOTICES + refreshed["warnings"] + cost_warnings)),
    )


def recommend(db: Session, account_id: str, product_id: str, review_id: UUID) -> AdviceReport:
    original = load(db, account_id, product_id, review_id)
    db.expire_all()
    current = load(db, account_id, product_id, review_id)
    if current != original:
        raise api_error(409, "PRICE_ADVICE_CHANGED", "Pricing evidence changed; try again.")
    return current
