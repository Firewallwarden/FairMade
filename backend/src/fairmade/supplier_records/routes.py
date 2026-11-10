"""Private supplier business records; no community directory or public rating route."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Response

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.pagination import Limit, Offset
from fairmade.private_http import NoStoreRoute
from fairmade.schemas import ErrorResponse, Page
from fairmade.supplier_records import repository, service
from fairmade.supplier_records.schemas import (
    ExperienceRequest,
    ExperienceResponse,
    ExperienceSummary,
    ProfileCreate,
    ProfileEventResponse,
    ProfileReplacement,
    ProfileResponse,
    ReliabilityResponse,
)

router = APIRouter(
    prefix="/api/v1/seller/suppliers",
    tags=["private supplier records"],
    route_class=NoStoreRoute,
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)


@router.post(
    "",
    response_model=ProfileEventResponse,
    status_code=201,
    responses={200: {"model": ProfileEventResponse, "description": "Existing exact retry"}},
)
def create(body: ProfileCreate, response: Response, db: DB, seller: VerifiedSeller):
    event, created = service.save_profile(db, seller.id, body)
    if not created:
        response.status_code = 200
    return event


@router.get("", response_model=Page[ProfileResponse])
def profiles(
    db: DB,
    seller: VerifiedSeller,
    archived: bool | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    return {
        "items": repository.profiles(db, seller.id, archived, limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{supplier_id}", response_model=ProfileResponse)
def profile(supplier_id: UUID, db: DB, seller: VerifiedSeller):
    return service.require_profile(db, seller.id, str(supplier_id))


@router.put("/{supplier_id}", response_model=ProfileEventResponse)
def replace(supplier_id: UUID, body: ProfileReplacement, db: DB, seller: VerifiedSeller):
    event, _created = service.save_profile(db, seller.id, body, str(supplier_id))
    return event


@router.get("/{supplier_id}/history", response_model=Page[ProfileEventResponse])
def history(
    supplier_id: UUID, db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0
):
    service.require_profile(db, seller.id, str(supplier_id))
    return {
        "items": repository.history(db, str(supplier_id), limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "/{supplier_id}/experiences",
    response_model=ExperienceResponse,
    status_code=201,
    responses={200: {"model": ExperienceResponse, "description": "Existing exact retry"}},
)
def record(
    supplier_id: UUID, body: ExperienceRequest, response: Response, db: DB, seller: VerifiedSeller
):
    record, created = service.save_experience(db, seller.id, str(supplier_id), body)
    if not created:
        response.status_code = 200
    return record


@router.get("/{supplier_id}/experiences", response_model=Page[ExperienceSummary])
def experiences(
    supplier_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    observed_from: date | None = None,
    observed_until: date | None = None,
    include_corrected: bool = False,
    limit: Limit = 20,
    offset: Offset = 0,
):
    service.require_profile(db, seller.id, str(supplier_id))
    service.validate_window(observed_from, observed_until)
    return {
        "items": repository.experiences(
            db, str(supplier_id), observed_from, observed_until, include_corrected, limit, offset
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{supplier_id}/experiences/{experience_id}", response_model=ExperienceResponse)
def experience(supplier_id: UUID, experience_id: UUID, db: DB, seller: VerifiedSeller):
    service.require_profile(db, seller.id, str(supplier_id))
    return service.require_experience(db, str(supplier_id), str(experience_id))


@router.get("/{supplier_id}/reliability", response_model=ReliabilityResponse)
def reliability(
    supplier_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    observed_from: date | None = None,
    observed_until: date | None = None,
):
    service.require_profile(db, seller.id, str(supplier_id))
    service.validate_window(observed_from, observed_until)
    return service.reliability(db, str(supplier_id), observed_from, observed_until)
