"""Bounded JPEG/PNG decoding and fresh-pixel JPEG output without source metadata."""

import hashlib
import struct
from dataclasses import dataclass
from io import BytesIO
from threading import BoundedSemaphore

from PIL import Image, ImageOps, UnidentifiedImageError

from fairmade.photos.errors import photo_error as api_error

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_INPUT_PIXELS = 16_000_000
MAX_INPUT_SIDE = 6000
MAX_OUTPUT_SIDE = 2048
_workers = BoundedSemaphore(2)
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG"}


@dataclass(frozen=True)
class NormalizedPhoto:
    data: bytes
    width: int
    height: int
    sha256: str


def normalize(data: bytes, media_type: str) -> NormalizedPhoto:
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise api_error(413, "PHOTO_SIZE_LIMIT", "Upload a nonempty image of at most 5 MiB.")
    if not _workers.acquire(blocking=False):
        error = api_error(429, "PHOTO_PROCESSING_BUSY", "Photo processing is busy; retry shortly.")
        error.headers = {"Retry-After": "1", "Cache-Control": "no-store"}
        raise error
    try:
        return _normalize(data, media_type)
    finally:
        _workers.release()


def _normalize(data: bytes, media_type: str) -> NormalizedPhoto:
    try:
        with Image.open(BytesIO(data), formats=["JPEG", "PNG"]) as image:
            if image.format != FORMATS.get(media_type):
                raise api_error(
                    415, "PHOTO_TYPE_MISMATCH", "Content type must match JPEG or PNG bytes."
                )
            width, height = image.size
            if (
                width > MAX_INPUT_SIDE
                or height > MAX_INPUT_SIDE
                or width * height > MAX_INPUT_PIXELS
            ):
                raise api_error(
                    422, "PHOTO_DIMENSION_LIMIT", "Photo dimensions exceed upload limits."
                )
            if getattr(image, "n_frames", 1) != 1:
                raise api_error(422, "ANIMATED_PHOTO", "Upload a single-frame image.")
            image.verify()
        with Image.open(BytesIO(data), formats=["JPEG", "PNG"]) as image:
            image.load()
            oriented = ImageOps.exif_transpose(image)
            oriented.thumbnail((MAX_OUTPUT_SIDE, MAX_OUTPUT_SIDE), Image.Resampling.LANCZOS)
            pixels = oriented.convert("RGBA")
            clean = Image.new("RGB", pixels.size, "white")
            clean.paste(pixels, mask=pixels.getchannel("A"))
            output = BytesIO()
            clean.save(output, format="JPEG", quality=85, exif=b"", icc_profile=None)
            encoded = output.getvalue()
            if len(encoded) > MAX_OUTPUT_BYTES:
                raise api_error(422, "PHOTO_OUTPUT_LIMIT", "Use a smaller or simpler photo.")
            return NormalizedPhoto(
                data=encoded,
                width=clean.width,
                height=clean.height,
                sha256=hashlib.sha256(encoded).hexdigest(),
            )
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        EOFError,
        struct.error,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise api_error(
            422, "INVALID_PHOTO", "Upload a valid, complete JPEG or PNG image."
        ) from None
