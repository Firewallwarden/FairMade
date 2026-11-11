import os
from uuid import uuid4

import pytest

from fairmade.assistants.gateway import OllamaGateway

pytestmark = pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local forecast conversation evaluation is opt-in.",
)


def test_real_forecast_saved_explanation_and_follow_up(
    paypal_client,
    market_headers,
    order_source,
    verified_sales,
):
    verified_sales()
    paypal_client.app.state.assistant_gateway = OllamaGateway()
    created = paypal_client.post(
        "/api/v1/assistants/conversations",
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {
                "role": "seller",
                "product_id": order_source["product"]["id"],
                "forecast": {},
            },
        },
    )
    assert created.status_code == 201, created.text
    for revision, question in enumerate(
        [
            "Explain the observed sales baseline and stock planning limitations.",
            "Why should I treat that as conditional rather than guaranteed demand?",
        ]
    ):
        response = paypal_client.post(
            "/api/v1/assistants/conversations/" + created.json()["id"] + "/turns",
            headers=market_headers,
            json={
                "request_id": str(uuid4()),
                "expected_revision": revision,
                "question": question,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
        assert any("2.250000" in fact["text"] for fact in response.json()["answer"]["facts"])
