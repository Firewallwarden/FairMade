"""Additive owner-only conversation APIs. Browser implementation is separate."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from fairmade.assistants.gateway import Gateway, get_gateway
from fairmade.auth import AUTH_ERRORS, DB, Authenticated, CurrentAccount
from fairmade.conversations import service
from fairmade.conversations.schemas import (
    ConversationPage,
    ConversationResponse,
    CreateConversation,
    CreateTurn,
    TurnPage,
    TurnResponse,
)
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/assistants/conversations",
    tags=["private assistant conversations"],
    route_class=NoStoreRoute,
    responses={
        **AUTH_ERRORS,
        **{code: {"model": ErrorResponse} for code in (403, 404, 409, 429, 502, 503)},
    },
)
Provider = Annotated[Gateway, Depends(get_gateway)]
Limit = Annotated[int, Query(ge=1, le=20)]
Offset = Annotated[int, Query(ge=0, le=1000)]


@router.post("", response_model=ConversationResponse, status_code=201)
def create(body: CreateConversation, db: DB, account: CurrentAccount, auth: Authenticated):
    return service.create(db, account.id, auth.token_hash, body)


@router.get("", response_model=ConversationPage)
def conversations(db: DB, account: CurrentAccount, limit: Limit = 20, offset: Offset = 0):
    return service.list_conversations(db, account.id, limit, offset)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get(conversation_id: UUID, db: DB, account: CurrentAccount, auth: Authenticated):
    return service.get(db, account.id, auth.token_hash, str(conversation_id))


@router.delete("/{conversation_id}", status_code=204)
def delete(conversation_id: UUID, db: DB, account: CurrentAccount):
    service.remove(db, account.id, str(conversation_id))
    return Response(status_code=204)


@router.get("/{conversation_id}/turns", response_model=TurnPage)
def turns(
    conversation_id: UUID,
    db: DB,
    account: CurrentAccount,
    auth: Authenticated,
    limit: Limit = 20,
    offset: Offset = 0,
):
    return service.list_turns(db, account.id, auth.token_hash, str(conversation_id), limit, offset)


@router.post("/{conversation_id}/turns", response_model=TurnResponse)
def ask(
    conversation_id: UUID,
    body: CreateTurn,
    db: DB,
    account: CurrentAccount,
    auth: Authenticated,
    gateway: Provider,
):
    return service.append(db, account.id, auth.token_hash, str(conversation_id), body, gateway)
