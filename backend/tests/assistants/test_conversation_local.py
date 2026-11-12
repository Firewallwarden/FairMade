"""Opt-in real two-turn evaluation on synthetic isolated data, including a restart."""

import os
import time
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from fairmade.assistants.gateway import OllamaGateway
from fairmade.main import create_app

pytestmark = pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local conversation evaluation is opt-in.",
)
PATH = "/api/v1/assistants/conversations"


@pytest.mark.parametrize("role", ["seller", "buyer"])
def test_real_two_turn_conversation_after_restart(
    market_client, market_url, market_headers, market_record, public_listing, role
):
    started = time.perf_counter()
    scope = (
        {"role": "seller", "product_id": market_record["product"]["id"]}
        if role == "seller"
        else {"role": "buyer", "listing_ids": [public_listing["id"]]}
    )
    created = market_client.post(
        PATH, headers=market_headers, json={"request_id": str(uuid4()), "scope": scope}
    )
    assert created.status_code == 201
    path = PATH + "/" + created.json()["id"] + "/turns"
    market_client.app.state.assistant_gateway = OllamaGateway()
    question = (
        "What happens if I charge $8 per loaf?"
        if role == "seller"
        else "Explain which labor cost information is missing for this loaf."
    )
    first = market_client.post(
        path,
        headers=market_headers,
        json={"request_id": str(uuid4()), "expected_revision": 0, "question": question},
    )
    assert first.status_code == 200, first.text
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = OllamaGateway()
        follow_up = (
            "Why does that price lose money?"
            if role == "seller"
            else "Why does that matter when deciding whether to buy it?"
        )
        second = restarted.post(
            path,
            headers=market_headers,
            json={"request_id": str(uuid4()), "expected_revision": 1, "question": follow_up},
        )
        assert second.status_code == 200, second.text
        result = second.json()
        assert result["context_turns"] == 1
        assert result["answer"]["role"] == role
        assert result["answer"]["paragraphs"]
        if role == "seller":
            scenarios = result["answer"]["evidence"][-1]["data"]["scenarios"]
            assert Decimal(scenarios[0]["price"]) == Decimal("8")
        else:
            assert "PRIVATE_MARKET" not in second.text
        assert len(restarted.get(path, headers=market_headers).json()["items"]) == 2
        print(
            f"LOCAL_CONVERSATION {role} two turns + restart "
            f"{time.perf_counter() - started:.2f}s {result['answer']['paragraphs']}"
        )
