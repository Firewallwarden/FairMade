"""Immediate author publication, frozen purchase evidence and exact rating arithmetic."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.models import ProductReview
from fairmade.product_reviews import repository
from fairmade.product_reviews.schemas import (
    OwnReview,
    PublicReview,
    RatingSummary,
    ReviewContent,
    ReviewUpdate,
)

NOTICES = [
    "Purchase evidence is a backend-verified sandbox capture recorded at review submission.",
    "Ratings/text are unverified buyer opinions, not quality certifications or fairness findings.",
    "Reviews publish immediately for local MVP; moderation and abuse controls need future work.",
]


def error(status: int, code: str, message: str) -> HTTPException:
    result = api_error(status, code, message)
    result.headers = {"Cache-Control": "no-store"}
    return result


def require_own(db: Session, buyer_id: str, review_id: str) -> ProductReview:
    review = repository.own(db, buyer_id, review_id)
    if review is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return review


def own_response(review: ProductReview) -> OwnReview:
    return OwnReview.model_validate(review)


def create(db: Session, buyer_id: str, order_id: str, listing_id: str, body: ReviewContent):
    source = repository.purchase(db, buyer_id, order_id, listing_id)
    if source is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    repository.reserve_purchase(db, buyer_id, order_id)
    source = repository.purchase(db, buyer_id, order_id, listing_id)
    if source is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    line, payment = source
    if (
        payment is None
        or payment.state != "completed"
        or not payment.capture_id
        or not payment.verified_at
    ):
        raise error(
            409, "PURCHASE_NOT_VERIFIED", "A backend-verified completed capture is required."
        )
    existing = repository.for_buyer_product(db, buyer_id, line.product_id)
    if existing is not None:
        if (
            existing.order_id == order_id
            and existing.listing_id == listing_id
            and existing.state == "published"
            and existing.rating == body.rating
            and existing.text == body.text
        ):
            db.commit()
            return existing, False
        raise error(
            409, "REVIEW_EXISTS", "Use your existing product review to edit or republish feedback."
        )
    review = ProductReview(
        buyer_account_id=buyer_id,
        product_id=line.product_id,
        order_id=order_id,
        listing_id=listing_id,
        order_line_id=line.id,
        revision=1,
        state="published",
        rating=body.rating,
        text=body.text,
        purchase_capture_id=payment.capture_id,
        purchase_verified_at=payment.verified_at,
    )
    db.add(review)
    db.commit()
    return review, True


def update(db: Session, buyer_id: str, review_id: str, body: ReviewUpdate) -> ProductReview:
    require_own(db, buyer_id, review_id)
    repository.reserve_review(db, buyer_id, review_id)
    review = require_own(db, buyer_id, review_id)
    same = review.state == "published" and review.rating == body.rating and review.text == body.text
    if same and body.expected_revision in (review.revision, review.revision - 1):
        db.commit()
        return review
    if review.revision != body.expected_revision:
        raise error(409, "REVISION_CONFLICT", "Review changed; reload before editing.")
    review.rating = body.rating
    review.text = body.text
    review.state = "published"
    review.revision += 1
    review.updated_at = utcnow()
    db.commit()
    return review


def withdraw(db: Session, buyer_id: str, review_id: str, revision: int) -> None:
    require_own(db, buyer_id, review_id)
    repository.reserve_review(db, buyer_id, review_id)
    review = require_own(db, buyer_id, review_id)
    if review.state == "withdrawn" and revision in (review.revision, review.revision - 1):
        db.commit()
        return
    if review.revision != revision:
        raise error(409, "REVISION_CONFLICT", "Review changed; reload before withdrawal.")
    review.state = "withdrawn"
    review.revision += 1
    review.updated_at = utcnow()
    db.commit()


def require_visible_listing(db: Session, listing_id: str) -> None:
    if repository.visible_listing(db, listing_id) is None:
        raise error(404, "NOT_FOUND", "Resource not found.")


def summary(db: Session, listing_id: str) -> RatingSummary:
    require_visible_listing(db, listing_id)
    count, total = repository.totals(db, listing_id)
    average = None
    if count:
        with localcontext() as context:
            context.prec = 40
            average = str(
                (Decimal(total) / Decimal(count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )
    return RatingSummary(review_count=count, average_rating=average, notices=NOTICES)


def public_response(review: ProductReview) -> PublicReview:
    return PublicReview.model_validate(review)
