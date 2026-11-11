"""Select owned saved evidence and persist an immutable private review."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller, api_error
from fairmade.database import utcnow
from fairmade.models import SellerPricingReview
from fairmade.products import Limit, Offset, owned_product
from fairmade.reviews.evidence import selected_evidence
from fairmade.reviews.schemas import ReviewRequest, ReviewResponse, ReviewSummary
from fairmade.reviews.service import REVIEW_VERSION, build_review
from fairmade.schemas import ErrorResponse, Page

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
    evidence = selected_evidence(db, product, body)
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
