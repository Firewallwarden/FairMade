"""Authenticated planning, with seller history restricted to its owning seller."""

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, CurrentAccount, VerifiedSeller
from fairmade.bundles.schemas import BundleReport, BundleRequest
from fairmade.bundles.service import suggest
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse

router = APIRouter(
    tags=["product bundle suggestions"],
    route_class=NoStoreRoute,
    responses={**AUTH_ERRORS, **{code: {"model": ErrorResponse} for code in (403, 404, 409)}},
)


@router.post("/api/v1/buyer/bundles/suggest", response_model=BundleReport)
def buyer(body: BundleRequest, db: DB, account: CurrentAccount):
    return suggest(db, account.id, body).result


@router.post("/api/v1/seller/bundles/suggest", response_model=BundleReport)
def seller(body: BundleRequest, db: DB, account: VerifiedSeller):
    return suggest(db, account.id, body, seller=True).result
