"""Authenticated assistant requests; no client-supplied evidence, history, URLs or tools."""

from typing import Annotated

from fastapi import APIRouter, Depends

from fairmade.assistants.gateway import Gateway, get_gateway
from fairmade.assistants.schemas import AssistantResponse, BuyerQuestion, SellerQuestion
from fairmade.assistants.service import answer
from fairmade.auth import AUTH_ERRORS, DB, Authenticated, CurrentAccount, VerifiedSeller
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/assistants",
    tags=["local AI assistants"],
    route_class=NoStoreRoute,
    responses={
        **AUTH_ERRORS,
        **{code: {"model": ErrorResponse} for code in (403, 404, 409, 429, 502, 503)},
    },
)
Provider = Annotated[Gateway, Depends(get_gateway)]


@router.post("/seller", response_model=AssistantResponse)
def seller_answer(
    body: SellerQuestion,
    db: DB,
    seller: VerifiedSeller,
    auth: Authenticated,
    gateway: Provider,
):
    return answer(db, seller.id, auth.token_hash, body, gateway)


@router.post("/buyer", response_model=AssistantResponse)
def buyer_answer(
    body: BuyerQuestion,
    db: DB,
    account: CurrentAccount,
    auth: Authenticated,
    gateway: Provider,
):
    return answer(db, account.id, auth.token_hash, body, gateway)
