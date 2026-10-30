import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fairmade.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def payload():
    example = Path(__file__).parents[1] / "examples" / "pricing-request.json"
    return json.loads(example.read_text(encoding="utf-8"))
