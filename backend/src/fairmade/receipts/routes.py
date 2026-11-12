"""Private seller receipt review and recorded expenses; no public receipt endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from fairmade.assistants.gateway import Gateway, get_gateway
from fairmade.auth import AUTH_ERRORS, DB, Authenticated, VerifiedSeller
from fairmade.models import ReceiptDraft, ReceiptExpense
from fairmade.pagination import Limit, Offset
from fairmade.private_http import NoStoreRoute
from fairmade.receipts import service
from fairmade.receipts.ocr import OCR, get_ocr
from fairmade.receipts.schemas import (
    ApproveReceipt,
    EditReceipt,
    ExpenseResponse,
    ImportReceipt,
    ReceiptResponse,
)
from fairmade.schemas import ErrorResponse, Page

router = APIRouter(
    prefix="/api/v1/seller",
    tags=["receipt expenses"],
    route_class=NoStoreRoute,
    responses={
        **AUTH_ERRORS,
        **{
            code: {"model": ErrorResponse}
            for code in (
                403,
                404,
                409,
                413,
                429,
                502,
                503,
            )
        },
    },
)
Provider = Annotated[Gateway, Depends(get_gateway)]
Reader = Annotated[OCR, Depends(get_ocr)]


@router.post("/receipt-drafts", response_model=ReceiptResponse, status_code=201)
def generate(
    body: ImportReceipt,
    db: DB,
    seller: VerifiedSeller,
    auth: Authenticated,
    gateway: Provider,
    reader: Reader,
):
    return service.generate(db, seller.id, auth.token_hash, body, gateway, reader)


@router.get("/receipt-drafts", response_model=Page[ReceiptResponse])
def browse(db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0):
    items = db.scalars(
        select(ReceiptDraft)
        .where(ReceiptDraft.account_id == seller.id)
        .order_by(
            ReceiptDraft.created_at.desc(),
            ReceiptDraft.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/receipt-drafts/{draft_id}", response_model=ReceiptResponse)
def get(draft_id: UUID, db: DB, seller: VerifiedSeller):
    return service.require_draft(db, seller.id, draft_id)


@router.put("/receipt-drafts/{draft_id}", response_model=ReceiptResponse)
def edit(draft_id: UUID, body: EditReceipt, db: DB, seller: VerifiedSeller):
    return service.edit(db, seller.id, draft_id, body)


@router.delete("/receipt-drafts/{draft_id}", status_code=204)
def discard(draft_id: UUID, db: DB, seller: VerifiedSeller):
    service.discard(db, seller.id, draft_id)
    return Response(status_code=204)


@router.post("/receipt-drafts/{draft_id}/approve", response_model=ExpenseResponse)
def approve(draft_id: UUID, body: ApproveReceipt, db: DB, seller: VerifiedSeller):
    return service.approve(db, seller.id, draft_id, body)


@router.get("/expenses", response_model=Page[ExpenseResponse])
def expenses(db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0):
    items = db.scalars(
        select(ReceiptExpense)
        .where(ReceiptExpense.account_id == seller.id)
        .order_by(
            ReceiptExpense.created_at.desc(),
            ReceiptExpense.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}
