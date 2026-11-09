"""Private seller material catalog and append-only quantity history."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.materials import repository, service
from fairmade.materials.schemas import (
    MaterialCreate,
    MaterialReplacement,
    MaterialResponse,
    MovementRequest,
    MovementResponse,
)
from fairmade.pagination import Limit, Offset
from fairmade.schemas import ErrorResponse, Page


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/seller/materials",
    tags=["manual material inventory"],
    dependencies=[Depends(no_store)],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)


@router.post("", response_model=MaterialResponse, status_code=201)
def create(body: MaterialCreate, db: DB, seller: VerifiedSeller):
    return service.material_response(service.create(db, seller.id, body))


@router.get("", response_model=Page[MaterialResponse])
def materials(db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0):
    return {
        "items": [
            service.material_response(material)
            for material in repository.materials(db, seller.id, limit, offset)
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{material_id}", response_model=MaterialResponse)
def material(material_id: UUID, db: DB, seller: VerifiedSeller):
    return service.material_response(service.require_owned(db, seller.id, str(material_id)))


@router.put("/{material_id}", response_model=MaterialResponse)
def replace(material_id: UUID, body: MaterialReplacement, db: DB, seller: VerifiedSeller):
    return service.material_response(service.replace(db, seller.id, str(material_id), body))


@router.post(
    "/{material_id}/movements",
    response_model=MovementResponse,
    status_code=201,
    responses={200: {"model": MovementResponse, "description": "Existing exact retry"}},
)
def record(
    material_id: UUID, body: MovementRequest, response: Response, db: DB, seller: VerifiedSeller
):
    event, created = service.record(db, seller.id, str(material_id), body)
    if not created:
        response.status_code = 200
    return service.movement_response(event)


@router.get("/{material_id}/movements", response_model=Page[MovementResponse])
def movements(
    material_id: UUID, db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0
):
    service.require_owned(db, seller.id, str(material_id))
    return {
        "items": [
            service.movement_response(event)
            for event in repository.movements(db, str(material_id), limit, offset)
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{material_id}/movements/{movement_id}", response_model=MovementResponse)
def movement(material_id: UUID, movement_id: UUID, db: DB, seller: VerifiedSeller):
    service.require_owned(db, seller.id, str(material_id))
    event = repository.movement(db, str(material_id), str(movement_id))
    if event is None:
        raise service.error(404, "NOT_FOUND", "Resource not found.")
    return service.movement_response(event)
