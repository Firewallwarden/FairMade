import os

import pytest

from fairmade.assistants.gateway import OllamaGateway

pytestmark = pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local personalization memory evaluation is opt-in.",
)


def test_real_remember_confirm_and_follow_up(
    market_client, buyer_headers, saved_buyer_turn, order_source
):
    class RecordingGateway(OllamaGateway):
        def complete(self, messages, schema):
            output = super().complete(messages, schema)
            if "budget_per_item" in schema["properties"]:
                print("SYNTHETIC_MEMORY_MODEL_OUTPUT", output)
            return output

    market_client.app.state.assistant_gateway = RecordingGateway()
    path = "/api/v1/buyer/personalization"
    proposal = market_client.post(path + "/remember", headers=buyer_headers, json=saved_buyer_turn)
    assert proposal.status_code == 200, proposal.text
    preferences = proposal.json()["preferences"]
    assert preferences["budget_per_item"] == "20"
    assert preferences["product_types"] == ["sourdough"]
    confirmed = market_client.put(
        path,
        headers=buyer_headers,
        json={
            "expected_revision": proposal.json()["profile_revision"],
            "enabled": True,
            "confirmed": True,
            "preferences": preferences,
        },
    )
    assert confirmed.status_code == 200
    explanation = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "listing_ids": [order_source["listing"]["id"]],
            "question": "Explain how this matches my remembered shopping preferences.",
        },
    )
    assert explanation.status_code == 200, explanation.text
    assert any("budget is USD 20" in fact["text"] for fact in explanation.json()["facts"])
    print(
        "LOCAL_PERSONALIZATION remembered budget, confirmed profile and current explanation passed."
    )
