"""Synthetic image decoding, metadata removal and bounded normalization."""

import hashlib
from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image, PngImagePlugin

from fairmade.photos import processing


def picture(format="PNG", size=(40, 20), **options):
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format=format, **options)
    return output.getvalue()


@pytest.mark.parametrize("format", ["JPEG", "PNG"])
def test_reencodes_pixels_to_jpeg_and_binds_hash_to_output(format):
    result = processing.normalize(picture(format), "image/" + format.lower())
    assert result.sha256 == hashlib.sha256(result.data).hexdigest()
    assert (result.width, result.height) == (40, 20)
    with Image.open(BytesIO(result.data)) as image:
        assert image.format == "JPEG" and not image.getexif()


def test_strips_private_text_exif_and_trailing_payload():
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "PRIVATE_GPS_TEXT")
    exif = Image.Exif()
    exif[270] = "PRIVATE_CAMERA_DESCRIPTION"
    data = picture(pnginfo=info, exif=exif) + b"PRIVATE_TRAILING_PAYLOAD"
    result = processing.normalize(data, "image/png")
    assert b"PRIVATE_" not in result.data
    with Image.open(BytesIO(result.data)) as image:
        assert not image.getexif() and "icc_profile" not in image.info


def test_exif_orientation_is_applied_then_removed():
    exif = Image.Exif()
    exif[274] = 6
    result = processing.normalize(picture("JPEG", exif=exif), "image/jpeg")
    assert (result.width, result.height) == (20, 40)
    with Image.open(BytesIO(result.data)) as image:
        assert not image.getexif()


def test_resizes_preserving_aspect_ratio_and_flattens_alpha():
    output = BytesIO()
    Image.new("RGBA", (3000, 1000), (0, 0, 0, 0)).save(output, format="PNG")
    result = processing.normalize(output.getvalue(), "image/png")
    assert result.width == 2048 and result.height == 683
    with Image.open(BytesIO(result.data)) as image:
        assert image.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize("data", [b"", b"<svg>PRIVATE_XML</svg>", b"not an image"])
def test_rejects_empty_or_nonimage_without_echoing(data):
    with pytest.raises(HTTPException) as raised:
        processing.normalize(data, "image/png")
    assert raised.value.status_code in (413, 422)
    assert "PRIVATE" not in str(raised.value.detail)


def test_rejects_type_mismatch_truncation_size_and_dimensions(monkeypatch):
    with pytest.raises(HTTPException) as error:
        processing.normalize(picture(), "image/jpeg")
    assert error.value.status_code == 415
    with pytest.raises(HTTPException):
        processing.normalize(picture("JPEG")[:100], "image/jpeg")
    monkeypatch.setattr(processing, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(HTTPException) as error:
        processing.normalize(picture(), "image/png")
    assert error.value.status_code == 413
    monkeypatch.setattr(processing, "MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
    monkeypatch.setattr(processing, "MAX_INPUT_PIXELS", 100)
    with pytest.raises(HTTPException) as error:
        processing.normalize(picture(), "image/png")
    assert error.value.detail["code"] == "PHOTO_DIMENSION_LIMIT"


def test_rejects_animated_png():
    output = BytesIO()
    Image.new("RGB", (10, 10), "red").save(
        output,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (10, 10), "blue")],
        duration=100,
    )
    with pytest.raises(HTTPException) as error:
        processing.normalize(output.getvalue(), "image/png")
    assert error.value.detail["code"] == "ANIMATED_PHOTO"


def test_concurrent_processor_limit_rejects_without_waiting():
    assert processing._workers.acquire(blocking=False)
    assert processing._workers.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as error:
            processing.normalize(picture(), "image/png")
        assert error.value.status_code == 429 and error.value.headers["Retry-After"] == "1"
    finally:
        processing._workers.release()
        processing._workers.release()
