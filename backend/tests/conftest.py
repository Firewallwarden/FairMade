import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fairmade.main import app

pytest_plugins = ["marketplace_fixtures", "order_fixtures"]


@pytest.fixture(autouse=True)
def disable_real_paypal(monkeypatch):
    monkeypatch.setenv("FAIRMADE_PAYPAL_ENABLED", "false")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def payload():
    example = Path(__file__).parents[1] / "examples" / "pricing-request.json"
    return json.loads(example.read_text(encoding="utf-8"))
