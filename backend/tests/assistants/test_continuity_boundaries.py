"""Audit: independent requests do not silently reuse an earlier conversation."""

import json


def test_independent_requests_do_not_replay_a_previous_price(
    market_client,
    market_headers,
    seller_question,
    ai_gateway,
):
    ai_gateway.prices = ["8"]
    first = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "question": "What happens if I charge $8 per loaf?",
        },
    )
    assert first.status_code == 200
    assert first.json()["evidence"][-1]["title"] == "Deterministic requested price scenarios"
    ai_gateway.calls.clear()
    ai_gateway.prices = []
    second = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "question": "Why does that price lose money?",
        },
    )
    assert second.status_code == 200
    assert not any(
        row["title"] == "Deterministic requested price scenarios"
        for row in second.json()["evidence"]
    )
    assert "$8" not in json.dumps(ai_gateway.calls)
