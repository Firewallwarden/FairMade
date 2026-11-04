"""General accounts can save, list and remove their own catalog bookmarks."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount
from fairmade.favorites import repository
from fairmade.favorites.schemas import FavoriteCreate, FavoriteResponse
from fairmade.pagination import Limit, Offset
from fairmade.schemas import ErrorResponse, Page


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/favorites",
    tags=["private favorites"],
    dependencies=[Depends(no_store)],
    responses={**AUTH_ERRORS, 404: {"model": ErrorResponse}},
)


@router.post(
    "",
    response_model=FavoriteResponse,
    status_code=201,
    responses={200: {"model": FavoriteResponse}},
)
def save(
    body: FavoriteCreate,
    db: DB,
    account: CurrentAccount,
    response: Response,
) -> FavoriteResponse:
    favorite, created = repository.create(db, account.id, body.listing_id)
    response.status_code = 201 if created else 200
    return favorite


@router.get("", response_model=Page[FavoriteResponse])
def list_favorites(
    db: DB,
    account: CurrentAccount,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    return {
        "items": repository.page(db, account.id, limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{favorite_id}", response_model=FavoriteResponse)
def get(favorite_id: UUID, db: DB, account: CurrentAccount) -> FavoriteResponse:
    return repository.get(db, account.id, favorite_id)


@router.delete("/{favorite_id}", status_code=204)
def remove(favorite_id: UUID, db: DB, account: CurrentAccount) -> Response:
    repository.remove(db, account.id, favorite_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
