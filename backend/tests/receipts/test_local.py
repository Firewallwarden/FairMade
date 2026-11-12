"""Opt-in real OCR + local model evaluation over synthetic isolated fixtures only."""

import base64
import os
import shutil
import time
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from fairmade.assistants.gateway import OllamaGateway
from fairmade.main import create_app

pytestmark = pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_RECEIPT_EVAL") != "true",
    reason="Real local Tesseract and Ollama receipt evaluation is opt-in.",
)


@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
def test_synthetic_receipt_to_reviewed_expense(
    market_client, market_url, market_headers, monkeypatch, image_format
):
    executable = os.environ.get("FAIRMADE_TESSERACT_PATH") or shutil.which("tesseract")
    assert executable and Path(executable).is_file(), (
        "The requested full receipt evaluation requires a configured Tesseract executable."
    )
    assert not hasattr(market_client.app.state, "receipt_ocr"), "Real OCR must not be replaced."
    monkeypatch.setenv("FAIRMADE_RECEIPTS_ENABLED", "true")
    market_client.app.state.assistant_gateway = OllamaGateway()
    image = Image.new("RGB", (1000, 700), "white")
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 36)
    ImageDraw.Draw(image).multiline_text(
        (40, 40),
        "SYNTHETIC STORE\n2026-11-10\nCurrency USD\nFlour     10.00\n"
        "SUBTOTAL  10.00\nTAX        0.80\nTOTAL     10.80",
        fill="black",
        font=font,
        spacing=12,
    )
    stream = BytesIO()
    image.save(stream, format=image_format)
    started = time.perf_counter()
    body = {
        "request_id": str(uuid4()),
        "image_base64": base64.b64encode(stream.getvalue()).decode(),
    }
    response = market_client.post(
        "/api/v1/seller/receipt-drafts",
        headers=market_headers,
        json=body,
    )
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["details"]["total"] == "10.80"
    assert draft["details"]["currency"] == "USD"
    assert draft["details"]["merchant"] == "SYNTHETIC STORE"
    assert draft["approval_blockers"] == []
    assert response.headers["Cache-Control"] == "no-store"
    assert body["image_base64"] not in response.text
    assert (
        market_client.post(
            "/api/v1/seller/receipt-drafts", headers=market_headers, json=body
        ).json()
        == draft
    )
    assert (
        market_client.get("/api/v1/seller/expenses", headers=market_headers).json()["items"] == []
    )
    path = "/api/v1/seller/receipt-drafts/" + draft["id"]
    edited = market_client.put(
        path,
        headers=market_headers,
        json={
            "expected_revision": draft["revision"],
            "details": {**draft["details"], "category": "materials"},
        },
    )
    assert edited.status_code == 200
    current = edited.json()
    approval = {
        "expected_revision": current["revision"],
        "preview_hash": current["preview_hash"],
        "approved": True,
    }
    stale = {
        **approval,
        "expected_revision": draft["revision"],
        "preview_hash": draft["preview_hash"],
    }
    assert (
        market_client.post(path + "/approve", headers=market_headers, json=stale).status_code == 409
    )
    approved = market_client.post(path + "/approve", headers=market_headers, json=approval)
    assert approved.status_code == 200
    expense = approved.json()
    assert expense["details"]["category"] == "materials"
    assert expense["details"]["total"] == "10.80"
    assert expense["basis"] == "seller_reviewed_unverified"
    assert (
        market_client.post(path + "/approve", headers=market_headers, json=approval).json()
        == expense
    )
    with TestClient(create_app(market_url)) as restarted:
        saved = restarted.get("/api/v1/seller/expenses", headers=market_headers)
        assert saved.status_code == 200 and saved.json()["items"] == [expense]
        assert restarted.get(path, headers=market_headers).json()["state"] == "approved"
    print(
        f"LOCAL_RECEIPT {image_format} real OCR/extraction/review/restart "
        f"{time.perf_counter() - started:.2f}s"
    )


def test_real_model_extracts_synthetic_ocr_text(
    market_client, market_headers, receipt_body, receipt_providers
):
    market_client.app.state.assistant_gateway = OllamaGateway()
    response = market_client.post(
        "/api/v1/seller/receipt-drafts",
        headers=market_headers,
        json=receipt_body,
    )
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["details"]["total"] == "10.80"
    assert draft["details"]["merchant"] == "SYNTHETIC STORE"
    assert draft["approval_blockers"] == []
