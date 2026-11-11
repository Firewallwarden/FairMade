import os
from uuid import uuid4

import pytest

from fairmade.assistants.gateway import OllamaGateway

from .conftest import save_profile

pytestmark = pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local basket conversation evaluation is opt-in.",
)


def test_real_basket_explanation_and_saved_follow_up(market_client, buyer_headers, basket_body):
    market_client.app.state.assistant_gateway = OllamaGateway()
    save_profile(market_client, buyer_headers, {"budget_per_item": "20"})
    created = market_client.post(
        "/api/v1/assistants/conversations",
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {"role": "buyer", "basket": basket_body},
        },
    )
    assert created.status_code == 201, created.text
    for revision, question in enumerate(
        [
            "Explain this shopping basket and its limitations.",
            "Why should I review those choices before checkout?",
        ]
    ):
        response = market_client.post(
            "/api/v1/assistants/conversations/" + created.json()["id"] + "/turns",
            headers=buyer_headers,
            json={
                "request_id": str(uuid4()),
                "expected_revision": revision,
                "question": question,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
        assert any("USD 31.00" in fact["text"] for fact in response.json()["answer"]["facts"])
