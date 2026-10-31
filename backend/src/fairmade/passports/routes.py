"""HTTP adapters for seller drafts and approved anonymous-safe publication."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.models import PassportDraft, PassportPublication
from fairmade.ownership import require_owned_product
from fairmade.pagination import Limit, Offset
from fairmade.passports import service
from fairmade.passports.errors import PassportError
from fairmade.passports.schemas import (
    DraftContent,
    DraftResponse,
    Preview,
    PublicationResponse,
    PublicPublication,
    PublishApproval,
    ReplaceDraft,
)
from fairmade.schemas import ErrorResponse, Page

router = APIRouter(
    prefix="/api/v1/products/{product_id}/passports",
    tags=["seller Passports"],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
public_router = APIRouter(prefix="/api/v1/passports", tags=["public Passports"])


async def passport_error_handler(_request: Request, exc: PassportError) -> JSONResponse:
    status = 404 if exc.code == "NOT_FOUND" else 409
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": exc.code, "message": exc.message}},
        headers={"Cache-Control": "no-store"},
    )


@router.post("", status_code=201, response_model=DraftResponse)
def create_draft(product_id: UUID, body: DraftContent, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.create_draft(db, product.id, body)


@router.get("", response_model=Page[DraftResponse])
def list_drafts(
    product_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
):
    product = require_owned_product(db, seller.id, product_id)
    items = db.scalars(
        select(PassportDraft)
        .where(PassportDraft.product_id == product.id)
        .order_by(PassportDraft.created_at.desc(), PassportDraft.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{draft_id}", response_model=DraftResponse)
def get_draft(product_id: UUID, draft_id: UUID, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.get_draft(db, product.id, str(draft_id))


@router.put("/{draft_id}", response_model=DraftResponse)
def replace_draft(
    product_id: UUID,
    draft_id: UUID,
    body: ReplaceDraft,
    db: DB,
    seller: VerifiedSeller,
):
    product = require_owned_product(db, seller.id, product_id)
    return service.replace_draft(db, product.id, str(draft_id), body)


@router.get("/{draft_id}/preview", response_model=Preview, response_model_exclude_none=True)
def preview(product_id: UUID, draft_id: UUID, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.preview(db, product.id, str(draft_id))


@router.post(
    "/{draft_id}/publish",
    status_code=201,
    response_model=PublicationResponse,
    response_model_exclude_none=True,
    responses={200: {"model": PublicationResponse}},
)
def publish(
    product_id: UUID,
    draft_id: UUID,
    body: PublishApproval,
    db: DB,
    seller: VerifiedSeller,
    response: Response,
):
    product = require_owned_product(db, seller.id, product_id)
    publication, created = service.publish(db, product.id, str(draft_id), body, seller.id)
    if not created:
        response.status_code = 200
    response.headers["Cache-Control"] = "no-store"
    return publication


@router.get(
    "/{draft_id}/publications",
    response_model=Page[PublicationResponse],
    response_model_exclude_none=True,
)
def list_publications(
    product_id: UUID,
    draft_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
):
    product = require_owned_product(db, seller.id, product_id)
    service.get_draft(db, product.id, str(draft_id))
    items = db.scalars(
        select(PassportPublication)
        .where(PassportPublication.draft_id == str(draft_id))
        .order_by(PassportPublication.created_at.desc(), PassportPublication.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.post("/{draft_id}/publications/{publication_id}/withdraw", status_code=204)
def withdraw(
    product_id: UUID,
    draft_id: UUID,
    publication_id: UUID,
    db: DB,
    seller: VerifiedSeller,
):
    product = require_owned_product(db, seller.id, product_id)
    service.withdraw(db, product.id, str(draft_id), str(publication_id))
    return Response(status_code=204)


@public_router.get(
    "/{publication_id}",
    response_model=PublicPublication,
    response_model_exclude_none=True,
    responses={404: {"model": ErrorResponse}},
)
def get_public(publication_id: UUID, db: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.get_publication(db, str(publication_id))
