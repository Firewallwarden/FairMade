"""Seller-only draft review; public publication remains a separate workflow."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from fairmade.assistants.gateway import Gateway, get_gateway
from fairmade.auth import AUTH_ERRORS, DB, Authenticated, VerifiedSeller
from fairmade.description_drafts import service
from fairmade.description_drafts.schemas import (
    ApproveDescription,
    DescriptionDraftResponse,
    EditDescription,
    GenerateDescription,
)
from fairmade.models import DescriptionDraft
from fairmade.ownership import require_owned_product
from fairmade.pagination import Limit, Offset
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse, Page

router = APIRouter(
    prefix="/api/v1/products/{product_id}/description-drafts",
    tags=["AI description drafts"],
    route_class=NoStoreRoute,
    responses={
        **AUTH_ERRORS,
        **{code: {"model": ErrorResponse} for code in (403, 404, 409, 429, 502, 503)},
    },
)
Provider = Annotated[Gateway, Depends(get_gateway)]


@router.post("", status_code=201, response_model=DescriptionDraftResponse)
def generate(
    product_id: UUID,
    body: GenerateDescription,
    db: DB,
    seller: VerifiedSeller,
    auth: Authenticated,
    gateway: Provider,
):
    return service.generate(db, seller.id, auth.token_hash, product_id, body, gateway)


@router.get("", response_model=Page[DescriptionDraftResponse])
def browse(product_id: UUID, db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0):
    product = require_owned_product(db, seller.id, product_id)
    items = db.scalars(
        select(DescriptionDraft)
        .where(DescriptionDraft.product_id == product.id)
        .order_by(DescriptionDraft.created_at.desc(), DescriptionDraft.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{draft_id}", response_model=DescriptionDraftResponse)
def get_draft(product_id: UUID, draft_id: UUID, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.require_draft(db, product.id, draft_id)


@router.put("/{draft_id}", response_model=DescriptionDraftResponse)
def edit(product_id: UUID, draft_id: UUID, body: EditDescription, db: DB, seller: VerifiedSeller):
    return service.edit(db, seller.id, product_id, draft_id, body)


@router.post("/{draft_id}/approve", response_model=DescriptionDraftResponse)
def approve(
    product_id: UUID, draft_id: UUID, body: ApproveDescription, db: DB, seller: VerifiedSeller
):
    return service.approve(db, seller.id, product_id, draft_id, body)
