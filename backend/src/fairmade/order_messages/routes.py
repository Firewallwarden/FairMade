"""Authenticated communication available only inside an existing owned order."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from fairmade.auth import AUTH_ERRORS, DB, Authenticated, CurrentAccount
from fairmade.order_messages import service
from fairmade.order_messages.schemas import MessagePage, MessageResponse, SendMessage
from fairmade.pagination import Limit
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/orders/{order_id}/messages",
    tags=["private order messages"],
    route_class=NoStoreRoute,
    responses={**AUTH_ERRORS, **{code: {"model": ErrorResponse} for code in (403, 404, 409, 429)}},
)


@router.post(
    "",
    response_model=MessageResponse,
    status_code=201,
    responses={200: {"model": MessageResponse, "description": "Identical send retry"}},
)
def send(
    order_id: UUID,
    body: SendMessage,
    db: DB,
    account: CurrentAccount,
    auth: Authenticated,
    response: Response,
):
    result, created = service.send(db, account.id, auth.token_hash, str(order_id), body)
    response.status_code = 201 if created else 200
    return result


@router.get("", response_model=MessagePage)
def history(
    order_id: UUID,
    db: DB,
    account: CurrentAccount,
    auth: Authenticated,
    after_sequence: Annotated[int, Query(ge=0, le=1000)] = 0,
    limit: Limit = 20,
):
    return service.history(db, account.id, auth.token_hash, str(order_id), after_sequence, limit)
