"""Bounded local Tesseract process over normalized, transient receipt images."""

import base64
import binascii
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import warnings
from io import BytesIO
from pathlib import Path
from typing import Protocol

from fastapi import Request
from PIL import Image, ImageOps, UnidentifiedImageError

from fairmade.auth import api_error

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TEXT_BYTES = 16000


class OCR(Protocol):
    def extract(self, image: bytes) -> str: ...


def normalize(encoded: str) -> tuple[bytes, str]:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise api_error(422, "INVALID_IMAGE", "Supply base64-encoded JPEG or PNG bytes.") from None
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise api_error(413, "RECEIPT_IMAGE_TOO_LARGE", "Receipt image must be at most five MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if (
                    source.format not in ("JPEG", "PNG")
                    or getattr(source, "n_frames", 1) != 1
                    or max(source.size) > 6000
                    or source.width * source.height > 12_000_000
                ):
                    raise ValueError
                oriented = ImageOps.exif_transpose(source).convert("RGBA")
                background = Image.new("RGBA", oriented.size, "white")
                background.alpha_composite(oriented)
                output = BytesIO()
                background.convert("L").save(output, format="PNG")
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise api_error(
            422, "INVALID_IMAGE", "Use one JPEG/PNG image within the dimension limits."
        ) from None
    return output.getvalue(), hashlib.sha256(raw).hexdigest()


def redact(text: str) -> str:
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise api_error(422, "RECEIPT_TEXT_TOO_LARGE", "Use a smaller single receipt.")
    payment = re.compile(
        r"\b(visa|mastercard|amex|card|acct|account|authorization|auth|terminal|cashier|tender)\b",
        re.I,
    )
    lines = [line for line in text.splitlines() if not payment.search(line)]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email redacted]", cleaned)
    cleaned = re.sub(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)", "[number redacted]", cleaned)
    if not cleaned.strip():
        raise api_error(422, "RECEIPT_TEXT_EMPTY", "No usable receipt text was recognized.")
    return cleaned.strip()


class Tesseract:
    def extract(self, image: bytes) -> str:
        executable = os.environ.get("FAIRMADE_TESSERACT_PATH") or shutil.which("tesseract")
        if not executable or not Path(executable).is_absolute() or not Path(executable).is_file():
            raise api_error(503, "OCR_UNAVAILABLE", "Configure a local Tesseract installation.")
        with tempfile.TemporaryDirectory(prefix="fairmade-receipt-") as directory:
            source = Path(directory) / "receipt.png"
            target = Path(directory) / "recognized"
            source.write_bytes(image)
            environment = {
                key: value
                for key, value in os.environ.items()
                if key.upper() in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "TESSDATA_PREFIX")
            }
            environment["OMP_THREAD_LIMIT"] = "1"
            try:
                result = subprocess.run(
                    [executable, str(source), str(target), "-l", "eng", "--psm", "6", "--oem", "1"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=20,
                    check=False,
                    env=environment,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise api_error(503, "OCR_UNAVAILABLE", "Local OCR failed or timed out.") from None
            output = target.with_suffix(".txt")
            if result.returncode != 0 or not output.is_file():
                raise api_error(503, "OCR_UNAVAILABLE", "Local OCR could not read the receipt.")
            with output.open("rb") as stream:
                raw = stream.read(MAX_TEXT_BYTES + 1)
            if len(raw) > MAX_TEXT_BYTES:
                raise api_error(422, "RECEIPT_TEXT_TOO_LARGE", "Use a smaller single receipt.")
            try:
                return redact(raw.decode("utf-8"))
            except UnicodeDecodeError:
                raise api_error(
                    502, "OCR_INVALID_RESPONSE", "Local OCR returned invalid text."
                ) from None


def get_ocr(request: Request) -> OCR:
    if os.environ.get("FAIRMADE_RECEIPTS_ENABLED") != "true":
        raise api_error(503, "RECEIPTS_DISABLED", "Receipt extraction is disabled.")
    return getattr(request.app.state, "receipt_ocr", None) or Tesseract()
