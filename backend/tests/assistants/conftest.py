import json

import pytest


class FakeGateway:
    def __init__(self):
        self.calls = []
        self.prices = []
        self.output = None
        self.after_answer = None

    def complete(self, messages, schema):
        self.calls.append({"messages": messages, "schema": schema})
        if "proposed_prices" in schema["properties"]:
            return {"proposed_prices": self.prices}
        if self.after_answer:
            self.after_answer()
        if self.output is not None:
            return self.output
        facts = json.loads(messages[-1]["content"])["EVIDENCE"]
        return {
            "paragraphs": [
                {
                    "text": "The selected evidence is seller-reported and unverified.",
                    "evidence_keys": [facts[0]["key"]],
                }
            ]
        }


@pytest.fixture
def ai_gateway(market_client):
    gateway = FakeGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def seller_question(market_record):
    return {
        "question": "Explain my costs and sustainable price range.",
        "product_id": market_record["product"]["id"],
        "analysis_id": market_record["analysis"]["id"],
    }


@pytest.fixture
def public_listing(market_client, market_headers, market_record, listing):
    path = market_record["path"] + "/listing"
    preview = market_client.get(path + "/preview", headers=market_headers).json()
    published = market_client.post(
        path + "/activate",
        headers=market_headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    )
    assert published.status_code == 200, published.text
    return listing
