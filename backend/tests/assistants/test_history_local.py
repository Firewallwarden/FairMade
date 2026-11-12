"""Opt-in synthetic local evaluation; no working database or external provider."""

import os
import re
import time

import pytest

from fairmade.assistants.gateway import OllamaGateway


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local model evaluation is opt-in.",
)
def test_real_history_question(market_client, market_headers, market_record):
    market_client.app.state.assistant_gateway = OllamaGateway()
    started = time.perf_counter()
    response = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            "product_id": market_record["product"]["id"],
            "question": "Explain my sales last month and any missing profit evidence.",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["evidence"][-2]["data"]["sales_count"] == 0
    text = " ".join(row["text"] for row in response.json()["paragraphs"])
    assert re.search(r"no (?:verified|recorded|completed|sales|captures)", text, re.IGNORECASE)
    print(f"LOCAL_HISTORY {time.perf_counter() - started:.2f}s {response.json()['paragraphs']}")
