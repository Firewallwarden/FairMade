"""Account-owned consent/preferences and public-catalog shopping suggestions."""

from typing import Annotated

from fastapi import APIRouter, Depends

from fairmade.assistants.gateway import Gateway, get_gateway
from fairmade.auth import AUTH_ERRORS, DB, Authenticated, CurrentAccount
from fairmade.personalization import memory, profiles, service
from fairmade.personalization.schemas import (
    DeleteProfile,
    MemoryProposal,
    MemoryRequest,
    ProfileResponse,
    Suggest,
    Suggestions,
    UpdateProfile,
)
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    prefix="/api/v1/buyer/personalization",
    tags=["buyer personalization"],
    route_class=NoStoreRoute,
    responses={
        **AUTH_ERRORS,
        **{
            code: {"model": ErrorResponse}
            for code in (
                404,
                409,
                429,
                502,
                503,
            )
        },
    },
)
Provider = Annotated[Gateway, Depends(get_gateway)]


@router.get("", response_model=ProfileResponse)
def get(db: DB, account: CurrentAccount):
    return profiles.get(db, account.id)


@router.put("", response_model=ProfileResponse)
def put(body: UpdateProfile, db: DB, account: CurrentAccount):
    return profiles.put(db, account.id, body)


@router.delete("", response_model=ProfileResponse)
def erase(body: DeleteProfile, db: DB, account: CurrentAccount):
    return profiles.erase(db, account.id, body.expected_revision)


@router.post("/suggestions", response_model=Suggestions)
def suggestions(body: Suggest, db: DB, account: CurrentAccount):
    return service.suggest(db, account.id, body)


@router.post("/remember", response_model=MemoryProposal)
def remember(
    body: MemoryRequest,
    db: DB,
    account: CurrentAccount,
    auth: Authenticated,
    gateway: Provider,
):
    return memory.propose(db, account.id, auth.token_hash, body, gateway)
