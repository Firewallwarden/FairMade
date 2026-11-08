"""General-account author operations; no seller approval, edit or suppression routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount
from fairmade.pagination import Limit, Offset
from fairmade.product_reviews import repository, service
from fairmade.product_reviews.schemas import (
    OwnReview,
    PublicReview,
    RatingSummary,
    ReviewContent,
    ReviewUpdate,
    WithdrawReview,
)
from fairmade.schemas import ErrorResponse, Page


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


ERRORS = {**AUTH_ERRORS, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}
purchase_router = APIRouter(
    prefix="/api/v1/orders",
    tags=["verified purchase feedback"],
    dependencies=[Depends(no_store)],
    responses=ERRORS,
)
author_router = APIRouter(
    prefix="/api/v1/account/product-reviews",
    tags=["own product reviews"],
    dependencies=[Depends(no_store)],
    responses=ERRORS,
)
public_router = APIRouter(
    prefix="/api/v1/marketplace/listings/{listing_id}/reviews",
    tags=["public product reviews"],
    dependencies=[Depends(no_store)],
    responses={404: {"model": ErrorResponse}},
)


@purchase_router.post(
    "/{order_id}/listings/{listing_id}/review",
    response_model=OwnReview,
    status_code=201,
    responses={200: {"model": OwnReview}},
)
def create(
    order_id: UUID,
    listing_id: UUID,
    body: ReviewContent,
    db: DB,
    buyer: CurrentAccount,
    response: Response,
):
    review, created = service.create(db, buyer.id, str(order_id), str(listing_id), body)
    response.status_code = 201 if created else 200
    return service.own_response(review)


@author_router.get("", response_model=Page[OwnReview])
def own_page(db: DB, buyer: CurrentAccount, limit: Limit = 20, offset: Offset = 0):
    return {
        "items": [
            service.own_response(row) for row in repository.own_page(db, buyer.id, limit, offset)
        ],
        "limit": limit,
        "offset": offset,
    }


@author_router.get("/{review_id}", response_model=OwnReview)
def own_get(review_id: UUID, db: DB, buyer: CurrentAccount):
    return service.own_response(service.require_own(db, buyer.id, str(review_id)))


@author_router.put("/{review_id}", response_model=OwnReview)
def update(review_id: UUID, body: ReviewUpdate, db: DB, buyer: CurrentAccount):
    return service.own_response(service.update(db, buyer.id, str(review_id), body))


@author_router.post("/{review_id}/withdraw", status_code=204)
def withdraw(review_id: UUID, body: WithdrawReview, db: DB, buyer: CurrentAccount):
    service.withdraw(db, buyer.id, str(review_id), body.expected_revision)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@public_router.get("", response_model=Page[PublicReview])
def public_page(listing_id: UUID, db: DB, limit: Limit = 20, offset: Offset = 0):
    service.require_visible_listing(db, str(listing_id))
    return {
        "items": [
            service.public_response(row)
            for row in repository.public_page(db, str(listing_id), limit, offset)
        ],
        "limit": limit,
        "offset": offset,
    }


@public_router.get("/summary", response_model=RatingSummary)
def summary(listing_id: UUID, db: DB):
    return service.summary(db, str(listing_id))
