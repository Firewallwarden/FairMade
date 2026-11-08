"""Administrator-only queue, detail and explicit final decision endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from fairmade.admin_review import repository, service
from fairmade.admin_review.schemas import AdminApplication, DecisionRequest
from fairmade.auth import AUTH_ERRORS, DB, Administrator
from fairmade.pagination import Limit, Offset
from fairmade.schemas import ErrorResponse, Page


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/admin/seller-applications",
    tags=["manual seller review"],
    dependencies=[Depends(no_store)],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)


@router.get("", response_model=Page[AdminApplication])
def queue(
    db: DB,
    admin: Administrator,
    state: Literal["pending", "approved", "denied", "all"] = "pending",
    limit: Limit = 20,
    offset: Offset = 0,
):
    return {
        "items": [
            service.admin_response(db, application, email)
            for application, email in repository.page(db, state, limit, offset)
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{application_id}", response_model=AdminApplication)
def detail(application_id: UUID, db: DB, admin: Administrator):
    return service.admin_response(db, service.require_application(db, str(application_id)))


@router.post("/{application_id}/decision", response_model=AdminApplication)
def decide(application_id: UUID, body: DecisionRequest, db: DB, admin: Administrator):
    return service.admin_response(db, service.decide(db, admin.id, str(application_id), body))
