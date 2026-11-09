import json
from pathlib import Path

import pytest


@pytest.fixture
def production_body():
    example = Path(__file__).parents[2] / "examples/production/bread.json"
    return json.loads(example.read_text(encoding="utf-8"))


@pytest.fixture
def production_product(market_client, market_headers):
    response = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={
            "name": "PRIVATE_PRODUCTION_PRODUCT",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    )
    assert response.status_code == 201
    return "/api/v1/products/" + response.json()["id"]
