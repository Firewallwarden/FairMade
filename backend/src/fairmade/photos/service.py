"""Reusable selection projection; immutable normalized bytes bind to listing approval hashes."""

import hashlib

from fastapi import Response
from sqlalchemy.orm import Session

from fairmade.models import ProductPhoto
from fairmade.photos import repository
from fairmade.photos.errors import photo_error as api_error
from fairmade.photos.schemas import PhotoSelection, PublicPhoto


def selected(
    db: Session, product_id: str, selections: list[PhotoSelection] | None
) -> list[PublicPhoto] | None:
    if selections is None:
        return None
    result = []
    for selection in selections:
        photo = repository.owned(db, product_id, selection.photo_id)
        result.append(
            PublicPhoto(
                id=photo.id,
                src=f"/api/v1/marketplace/photos/{photo.id}",
                alt_text=selection.alt_text,
                width=photo.width,
                height=photo.height,
                sha256=photo.sha256,
            )
        )
    return result


def image_response(photo: ProductPhoto) -> Response:
    if (
        len(photo.image_bytes) != photo.byte_count
        or hashlib.sha256(photo.image_bytes).hexdigest() != photo.sha256
    ):
        error = api_error(503, "PHOTO_UNAVAILABLE", "Photo content is unavailable.")
        error.headers = {"Cache-Control": "no-store"}
        raise error
    return Response(
        content=photo.image_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Disposition": f'inline; filename="{photo.id}.jpg"',
        },
    )
