import base64
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

TEXT = "SYNTHETIC STORE\n2026-11-10\nUSD\nFlour 10.00\nSUBTOTAL 10.00\nTAX 0.80\nTOTAL 10.80"


class FakeOCR:
    text = TEXT

    def __init__(self):
        self.calls = 0

    def extract(self, image):
        assert image.startswith(b"\x89PNG")
        self.calls += 1
        return self.text


class FakeGateway:
    def __init__(self):
        self.calls = []
        self.after = None
        self.output = {
            "merchant": "SYNTHETIC STORE",
            "date_text": "2026-11-10",
            "currency": "USD",
            "subtotal": "10.00",
            "tax": "0.80",
            "total": "10.80",
            "items": [{"description": "Flour", "line_total": "10.00"}],
        }

    def complete(self, messages, schema):
        self.calls.append(messages)
        if self.after:
            self.after()
        return self.output


@pytest.fixture
def receipt_providers(market_client, monkeypatch):
    monkeypatch.setenv("FAIRMADE_RECEIPTS_ENABLED", "true")
    gateway, reader = FakeGateway(), FakeOCR()
    market_client.app.state.assistant_gateway = gateway
    market_client.app.state.receipt_ocr = reader
    return gateway, reader


@pytest.fixture
def receipt_body():
    image = Image.new("RGB", (800, 600), "white")
    content = BytesIO()
    image.save(content, format="PNG")
    return {
        "request_id": str(uuid4()),
        "image_base64": base64.b64encode(content.getvalue()).decode(),
    }
