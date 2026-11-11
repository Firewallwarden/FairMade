import json

from .conftest import send


def test_withdrawn_listing_does_not_remove_order_communication(
    market_client,
    buyer_headers,
    market_headers,
    message_path,
    order_source,
):
    assert (
        market_client.post(
            order_source["path"] + "/listing/deactivate", headers=market_headers
        ).status_code
        == 204
    )
    assert send(market_client, buyer_headers, message_path).status_code == 201
    assert len(market_client.get(message_path, headers=market_headers).json()["items"]) == 1


def test_human_messages_are_not_assistant_evidence(
    market_client,
    buyer_headers,
    market_headers,
    message_path,
    order_source,
):
    marker = "PRIVATE_HUMAN_ORDER_MESSAGE"
    assert send(market_client, buyer_headers, message_path, marker).status_code == 201

    class Gateway:
        def __init__(self):
            self.calls = []

        def complete(self, messages, schema):
            self.calls.append(messages)
            if "proposed_prices" in schema["properties"]:
                return {"proposed_prices": []}
            facts = json.loads(messages[-1]["content"])["EVIDENCE"]
            return {
                "paragraphs": [
                    {"text": "Review the supplied evidence.", "evidence_keys": [facts[0]["key"]]}
                ]
            }

    gateway = Gateway()
    market_client.app.state.assistant_gateway = gateway
    for role, headers, scope in [
        ("buyer", buyer_headers, {"listing_ids": [order_source["listing"]["id"]]}),
        ("seller", market_headers, {"product_id": order_source["product"]["id"]}),
    ]:
        response = market_client.post(
            "/api/v1/assistants/" + role,
            headers=headers,
            json={"question": "Explain the selected evidence.", **scope},
        )
        assert response.status_code == 200, response.text
        assert marker not in response.text
    assert marker not in json.dumps(gateway.calls)
