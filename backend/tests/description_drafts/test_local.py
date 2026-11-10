import os
from uuid import uuid4

import pytest

from fairmade.assistants.gateway import OllamaGateway


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local model evaluation is opt-in.",
)
def test_real_description_is_a_private_reviewable_draft(market_client, market_headers):
    product = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={
            "name": "Example sourdough",
            "product_type": "sourdough",
            "selling_unit": "loaf",
            "description": "A sourdough loaf sold individually.",
        },
    )
    assert product.status_code == 201
    market_client.app.state.assistant_gateway = OllamaGateway()
    path = "/api/v1/products/" + product.json()["id"]
    result = market_client.post(
        path + "/description-drafts",
        headers=market_headers,
        json={"request_id": str(uuid4()), "tone": "plain"},
    )
    assert result.status_code == 201, result.text
    assert result.json()["state"] == "draft"
    assert (
        market_client.get(path, headers=market_headers).json()["description"]
        == product.json()["description"]
    )
    print("LOCAL_DESCRIPTION_DRAFT", result.json()["description"])
