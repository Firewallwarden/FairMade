"""Seller-private livestock profiles, recorded history and attributed production."""

from uuid import UUID

from fastapi import APIRouter, Response

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.livestock import repository, service
from fairmade.livestock.schemas import (
    AnimalCreate,
    AnimalReplacement,
    AnimalResponse,
    AnimalStatus,
    GroupCreate,
    GroupReplacement,
    GroupResponse,
    HistoryResponse,
)
from fairmade.pagination import Limit, Offset
from fairmade.private_http import NoStoreRoute
from fairmade.production import repository as production_repository
from fairmade.production.schemas import ProductionSummary
from fairmade.schemas import ErrorResponse, Page

router = APIRouter(
    prefix="/api/v1/seller/livestock",
    tags=["livestock"],
    route_class=NoStoreRoute,
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)


@router.post(
    "/groups",
    response_model=HistoryResponse,
    status_code=201,
    responses={200: {"model": HistoryResponse, "description": "Existing exact retry"}},
)
def create_group(body: GroupCreate, response: Response, db: DB, seller: VerifiedSeller):
    event, created = service.save_group(db, seller.id, body)
    if not created:
        response.status_code = 200
    return service.history_response(event)


@router.get("/groups", response_model=Page[GroupResponse])
def groups(
    db: DB,
    seller: VerifiedSeller,
    archived: bool | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    rows = repository.groups(db, seller.id, archived, limit, offset)
    return {
        "items": [service.group_response(group, count) for group, count in rows],
        "limit": limit,
        "offset": offset,
    }


@router.get("/groups/{group_id}", response_model=GroupResponse)
def group(group_id: UUID, db: DB, seller: VerifiedSeller):
    resource = service.require_group(db, seller.id, str(group_id))
    return service.group_response(resource, repository.registered_count(db, seller.id, resource.id))


@router.put("/groups/{group_id}", response_model=HistoryResponse)
def replace_group(group_id: UUID, body: GroupReplacement, db: DB, seller: VerifiedSeller):
    event, _created = service.save_group(db, seller.id, body, str(group_id))
    return service.history_response(event)


@router.get("/groups/{group_id}/history", response_model=Page[HistoryResponse])
def group_history(
    group_id: UUID, db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0
):
    service.require_group(db, seller.id, str(group_id))
    return {
        "items": [
            service.history_response(event)
            for event in repository.group_history(db, str(group_id), limit, offset)
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "/animals",
    response_model=HistoryResponse,
    status_code=201,
    responses={200: {"model": HistoryResponse, "description": "Existing exact retry"}},
)
def create_animal(body: AnimalCreate, response: Response, db: DB, seller: VerifiedSeller):
    event, created = service.save_animal(db, seller.id, body)
    if not created:
        response.status_code = 200
    return service.history_response(event)


@router.get("/animals", response_model=Page[AnimalResponse])
def animals(
    db: DB,
    seller: VerifiedSeller,
    group_id: UUID | None = None,
    status: AnimalStatus | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    if group_id is not None:
        service.require_group(db, seller.id, str(group_id))
    rows = repository.animals(
        db, seller.id, str(group_id) if group_id else None, status, limit, offset
    )
    return {"items": rows, "limit": limit, "offset": offset}


@router.get("/animals/{animal_id}", response_model=AnimalResponse)
def animal(animal_id: UUID, db: DB, seller: VerifiedSeller):
    return service.require_animal(db, seller.id, str(animal_id))


@router.put("/animals/{animal_id}", response_model=HistoryResponse)
def replace_animal(animal_id: UUID, body: AnimalReplacement, db: DB, seller: VerifiedSeller):
    event, _created = service.save_animal(db, seller.id, body, str(animal_id))
    return service.history_response(event)


@router.get("/animals/{animal_id}/history", response_model=Page[HistoryResponse])
def animal_history(
    animal_id: UUID, db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0
):
    service.require_animal(db, seller.id, str(animal_id))
    return {
        "items": [
            service.history_response(event)
            for event in repository.animal_history(db, str(animal_id), limit, offset)
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/groups/{group_id}/production-records", response_model=Page[ProductionSummary])
def group_production(
    group_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    include_corrected: bool = False,
    limit: Limit = 20,
    offset: Offset = 0,
):
    service.require_group(db, seller.id, str(group_id))
    return {
        "items": production_repository.page(
            db, None, include_corrected, limit, offset, account_id=seller.id, group_id=str(group_id)
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/animals/{animal_id}/production-records", response_model=Page[ProductionSummary])
def animal_production(
    animal_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    include_corrected: bool = False,
    limit: Limit = 20,
    offset: Offset = 0,
):
    service.require_animal(db, seller.id, str(animal_id))
    return {
        "items": production_repository.page(
            db,
            None,
            include_corrected,
            limit,
            offset,
            account_id=seller.id,
            animal_id=str(animal_id),
        ),
        "limit": limit,
        "offset": offset,
    }
