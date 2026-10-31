"""Select owned saved evidence and persist an immutable private review."""

from uuid import UUID

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller, api_error
from fairmade.comparisons.schemas import ReportResponse
from fairmade.comparisons.service import COMPARISON_VERSION
from fairmade.comparisons.units import named_unit_matches
from fairmade.database import utcnow
from fairmade.models import (
    Analysis,
    PriceComparison,
    QualityEvaluation,
    QualityLockSet,
    SellerPricingReview,
)
from fairmade.products import Limit, Offset, owned_product
from fairmade.quality.schemas import EvaluationResponse
from fairmade.quality.service import EVALUATION_VERSION
from fairmade.reviews.schemas import ReviewRequest, ReviewResponse, ReviewSummary
from fairmade.reviews.service import REVIEW_VERSION, build_review
from fairmade.schemas import AnalysisResponse, ErrorResponse, Page, ProductResponse

router = APIRouter(
    prefix="/api/v1/products/{product_id}/pricing-reviews",
    tags=["seller pricing reviews"],
    responses={**AUTH_ERRORS, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)


@router.post(
    "", status_code=201, response_model=ReviewResponse, responses={409: {"model": ErrorResponse}}
)
def create_review(
    product_id: UUID,
    body: ReviewRequest,
    db: DB,
    seller: VerifiedSeller,
) -> SellerPricingReview:
    product = owned_product(db, seller, product_id)
    analysis = db.scalar(
        select(Analysis).where(
            Analysis.id == str(body.pricing_analysis_id),
            Analysis.product_id == product.id,
        )
    )
    comparison = None
    if body.comparison_report_id:
        comparison = db.scalar(
            select(PriceComparison).where(
                PriceComparison.id == str(body.comparison_report_id),
                PriceComparison.product_id == product.id,
            )
        )
    evaluations = db.scalars(
        select(QualityEvaluation).where(
            QualityEvaluation.product_id == product.id,
            QualityEvaluation.id.in_([str(value) for value in body.quality_evaluation_ids]),
        )
    ).all()
    if (
        analysis is None
        or (body.comparison_report_id and comparison is None)
        or len(evaluations) != len(body.quality_evaluation_ids)
    ):
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    if (
        analysis.calculation_version != "production-economics-v1"
        or analysis.result.get("calculation_version") != "production-economics-v1"
        or (comparison and comparison.comparison_version != COMPARISON_VERSION)
        or any(item.evaluation_version != EVALUATION_VERSION for item in evaluations)
    ):
        raise api_error(
            409, "UNSUPPORTED_EVIDENCE_VERSION", "Selected evidence uses an unsupported version."
        )
    if body.production_unit_quantity and not named_unit_matches(
        analysis.product_snapshot["product_type"],
        body.production_unit_quantity.unit,
    ):
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "production_unit_quantity", "unit"),
                    "msg": "Named units must match the saved pricing product type",
                    "input": body.production_unit_quantity.unit,
                }
            ]
        )
    current = db.get(QualityLockSet, product.id)
    by_id = {item.id: item for item in evaluations}
    evidence = {
        "product": ProductResponse.model_validate(product).model_dump(mode="json"),
        "pricing_analysis": AnalysisResponse.model_validate(analysis).model_dump(mode="json"),
        "quality_lock_set": {
            "revision": current.revision if current else 0,
            "rules": current.rules if current else [],
        },
        "quality_evaluations": [
            EvaluationResponse.model_validate(by_id[str(value)]).model_dump(mode="json")
            for value in body.quality_evaluation_ids
        ],
        "comparison_report": ReportResponse.model_validate(comparison).model_dump(mode="json")
        if comparison
        else None,
    }
    reviewed_on = utcnow().date()
    review = SellerPricingReview(
        product_id=product.id,
        reviewed_on=reviewed_on,
        review_version=REVIEW_VERSION,
        basis="seller_reported_unverified",
        request_snapshot=body.model_dump(mode="json"),
        evidence_snapshot=evidence,
        result=build_review(body, evidence, reviewed_on),
    )
    db.add(review)
    db.commit()
    return review


@router.get("", response_model=Page[ReviewSummary])
def list_reviews(
    product_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    product = owned_product(db, seller, product_id)
    items = db.scalars(
        select(SellerPricingReview)
        .where(SellerPricingReview.product_id == product.id)
        .order_by(SellerPricingReview.created_at.desc(), SellerPricingReview.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(
    product_id: UUID,
    review_id: UUID,
    db: DB,
    seller: VerifiedSeller,
) -> SellerPricingReview:
    product = owned_product(db, seller, product_id)
    review = db.scalar(
        select(SellerPricingReview).where(
            SellerPricingReview.id == str(review_id),
            SellerPricingReview.product_id == product.id,
        )
    )
    if review is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return review
