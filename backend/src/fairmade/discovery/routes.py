"""Anonymous read-only POST searches; origins are never persisted or echoed."""

from fastapi import APIRouter, Depends, Response

from fairmade.auth import DB
from fairmade.discovery import service
from fairmade.discovery.schemas import (
    AreaSearch,
    DiscoveryPage,
    ListingSearch,
    NearbyListing,
    NearbyStorefront,
)
from fairmade.schemas import ErrorResponse


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/discovery",
    tags=["public approximate-area discovery"],
    dependencies=[Depends(no_store)],
    responses={409: {"model": ErrorResponse}},
)


@router.post(
    "/storefronts", response_model=DiscoveryPage[NearbyStorefront], response_model_exclude_none=True
)
def storefronts(body: AreaSearch, db: DB) -> dict:
    return service.storefronts(db, body)


@router.post(
    "/listings", response_model=DiscoveryPage[NearbyListing], response_model_exclude_none=True
)
def listings(body: ListingSearch, db: DB) -> dict:
    return service.listings(db, body)
