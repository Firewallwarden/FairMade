"""Opt-in real OCR + local model evaluation over synthetic isolated fixtures only."""

import base64
import os
import shutil
import time
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw, ImageFont

from fairmade.assistants.gateway import OllamaGateway

pytestmark = pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_RECEIPT_EVAL") != "true",
    reason="Real local Tesseract and Ollama receipt evaluation is opt-in.",
)


@pytest.mark.skipif(
    not (os.environ.get("FAIRMADE_TESSERACT_PATH") or shutil.which("tesseract")),
    reason="A configured Tesseract executable is required for the full OCR smoke test.",
)
def test_synthetic_receipt_to_reviewed_expense(market_client, market_headers, monkeypatch):
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
    image.save(stream, format="PNG")
    started = time.perf_counter()
    response = market_client.post(
        "/api/v1/seller/receipt-drafts",
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "image_base64": base64.b64encode(stream.getvalue()).decode(),
        },
    )
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["details"]["total"] == "10.80"
    assert draft["details"]["currency"] == "USD"
    assert draft["details"]["merchant"] == "SYNTHETIC STORE"
    assert draft["approval_blockers"] == []
    assert (
        market_client.get("/api/v1/seller/expenses", headers=market_headers).json()["items"] == []
    )
    approved = market_client.post(
        "/api/v1/seller/receipt-drafts/" + draft["id"] + "/approve",
        headers=market_headers,
        json={
            "expected_revision": draft["revision"],
            "preview_hash": draft["preview_hash"],
            "approved": True,
        },
    )
    assert approved.status_code == 200
    print(f"LOCAL_RECEIPT synthetic OCR/extraction/review {time.perf_counter() - started:.2f}s")


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
