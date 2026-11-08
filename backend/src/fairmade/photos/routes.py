"""Bounded raw uploads avoid multipart spooling and never use client filenames or URLs."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from starlette.concurrency import run_in_threadpool

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.ownership import require_owned_product
from fairmade.pagination import Limit, Offset
from fairmade.photos import processing, repository, service
from fairmade.photos.errors import photo_error as api_error
from fairmade.photos.schemas import PhotoMetadata
from fairmade.schemas import ErrorResponse, Page


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/products/{product_id}/photos",
    tags=["private product photos"],
    dependencies=[Depends(no_store)],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
public_router = APIRouter(
    prefix="/api/v1/marketplace/photos",
    tags=["approved public photos"],
    responses={404: {"model": ErrorResponse}},
)


@router.post(
    "",
    status_code=201,
    response_model=PhotoMetadata,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in ("image/jpeg", "image/png")
            },
        }
    },
)
async def upload(product_id: UUID, request: Request, db: DB, seller: VerifiedSeller):
    product = await run_in_threadpool(require_owned_product, db, seller.id, product_id)
    product_key, account_key = product.id, seller.id
    media_type = request.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if (
        media_type not in processing.FORMATS
        or request.headers.get("Content-Encoding", "identity") != "identity"
    ):
        raise api_error(
            415, "UNSUPPORTED_PHOTO_TYPE", "Send raw JPEG or PNG bytes without compression."
        )
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > processing.MAX_UPLOAD_BYTES:
            raise api_error(413, "PHOTO_SIZE_LIMIT", "Upload at most 5 MiB.")
        chunks.extend(chunk)
    image = await run_in_threadpool(processing.normalize, bytes(chunks), media_type)
    return await run_in_threadpool(repository.save, db, product_key, account_key, image)


@router.get("", response_model=Page[PhotoMetadata])
def photos(product_id: UUID, db: DB, seller: VerifiedSeller, limit: Limit = 20, offset: Offset = 0):
    product = require_owned_product(db, seller.id, product_id)
    return {
        "items": repository.page(db, product.id, limit, offset),
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{photo_id}/content",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}},
        503: {"model": ErrorResponse},
    },
)
def private_content(product_id: UUID, photo_id: UUID, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    return service.image_response(repository.owned(db, product.id, photo_id, with_bytes=True))


@router.delete("/{photo_id}", status_code=204)
def remove(product_id: UUID, photo_id: UUID, db: DB, seller: VerifiedSeller):
    product = require_owned_product(db, seller.id, product_id)
    repository.remove(db, product.id, photo_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@public_router.get(
    "/{photo_id}",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}},
        503: {"model": ErrorResponse},
    },
)
def public_content(photo_id: UUID, db: DB):
    return service.image_response(repository.public_photo(db, photo_id))
