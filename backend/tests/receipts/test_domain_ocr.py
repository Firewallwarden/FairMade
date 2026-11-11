import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from fairmade.receipts.domain import initial_details, review_issues
from fairmade.receipts.ocr import Tesseract, normalize, redact


def test_unknown_dates_remain_unknown_and_exact_reconciliation():
    assert initial_details({"date_text": "02/03/2026"})["purchased_on"] is None
    assert initial_details({"date_text": "2026-02-30"})["purchased_on"] is None
    assert initial_details({"date_text": "2026-02-03"})["purchased_on"] == "2026-02-03"
    details = {
        "merchant": "Store",
        "purchased_on": "2026-11-10",
        "currency": "USD",
        "total": "0.30",
        "subtotal": "0.30",
        "tax": "0.00",
        "items": [{"line_total": "0.10"}, {"line_total": "0.20"}],
    }
    assert review_issues(details) == []
    details["subtotal"] = "0.29"
    assert set(review_issues(details)) == {"TOTAL_MISMATCH", "ITEM_TOTAL_MISMATCH"}


def test_normalization_strips_metadata_and_enforces_formats(receipt_body):
    from io import BytesIO

    normalized, source_hash = normalize(receipt_body["image_base64"])
    assert len(source_hash) == 64
    with Image.open(BytesIO(normalized)) as image:
        assert image.mode == "L" and image.info == {}
    with pytest.raises(HTTPException):
        normalize("not-base64")


@pytest.mark.parametrize("failure", ["timeout", "exit", "oversized", "empty"])
def test_tesseract_failure_is_bounded_and_temporary_files_removed(
    tmp_path, monkeypatch, receipt_body, failure
):
    executable = tmp_path / "tesseract.exe"
    executable.touch()
    monkeypatch.setenv("FAIRMADE_TESSERACT_PATH", str(executable))
    locations = []

    def run(args, **kwargs):
        locations.append(Path(args[1]).parent)
        assert kwargs["timeout"] == 20
        assert args[-6:] == ["-l", "eng", "--psm", "6", "--oem", "1"]
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 20)
        Path(args[2] + ".txt").write_text(
            "x" * 16001 if failure == "oversized" else "", encoding="utf-8"
        )
        return SimpleNamespace(returncode=1 if failure == "exit" else 0)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(HTTPException):
        Tesseract().extract(normalize(receipt_body["image_base64"])[0])
    assert locations and not locations[0].exists()


def test_missing_engine_and_redacted_text(monkeypatch):
    monkeypatch.setenv("FAIRMADE_TESSERACT_PATH", "/missing/tesseract")
    with pytest.raises(HTTPException) as error:
        Tesseract().extract(b"image")
    assert error.value.status_code == 503
    assert redact("Store\nUSD TOTAL 10.80\nVISA 4111111111111111") == "Store\nUSD TOTAL 10.80"
