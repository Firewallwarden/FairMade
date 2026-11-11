import json
from uuid import uuid4

import pytest

PATH = "/api/v1/buyer/personalization"


class FakeGateway:
    def __init__(self):
        self.calls = []
        self.output = {"budget_per_item": "20", "product_types": ["sourdough"]}
        self.after = None

    def complete(self, messages, schema):
        self.calls.append(messages)
        if self.after:
            self.after()
        if "budget_per_item" in schema["properties"]:
            return self.output
        if "proposed_prices" in schema["properties"]:
            return {"proposed_prices": []}
        facts = json.loads(messages[-1]["content"])["EVIDENCE"]
        return {
            "paragraphs": [
                {
                    "text": "Use the current evidence and confirmed preferences.",
                    "evidence_keys": [facts[0]["key"]],
                }
            ]
        }


@pytest.fixture
def profile_gateway(market_client):
    gateway = FakeGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def enabled_profile(market_client, buyer_headers):
    response = market_client.put(
        PATH,
        headers=buyer_headers,
        json={"expected_revision": 0, "enabled": True, "confirmed": True, "preferences": {}},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def saved_buyer_turn(market_client, buyer_headers, order_source, enabled_profile, profile_gateway):
    conversation = market_client.post(
        "/api/v1/assistants/conversations",
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {
                "role": "buyer",
                "listing_ids": [order_source["listing"]["id"]],
            },
        },
    )
    assert conversation.status_code == 201, conversation.text
    identifier = conversation.json()["id"]
    response = market_client.post(
        "/api/v1/assistants/conversations/" + identifier + "/turns",
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": 0,
            "question": "My budget is $20 per item and I prefer sourdough bread.",
        },
    )
    assert response.status_code == 200, response.text
    return {"conversation_id": identifier, "turn_id": response.json()["id"]}
