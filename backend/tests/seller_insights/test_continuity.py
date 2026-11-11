"""Private insights survive saved dialogue while evidence and access remain current."""

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from fairmade.main import create_app
from fairmade.seller_insights.integration import TITLE


def conversation(client, headers, source):
    response = client.post(
        "/api/v1/assistants/conversations",
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "scope": {
                "role": "seller",
                "product_id": source["product"]["id"],
                "insights": {"period_days": 30},
            },
        },
    )
    assert response.status_code == 201
    return "/api/v1/assistants/conversations/" + response.json()["id"] + "/turns"


def turn(client, headers, path, revision, question):
    return client.post(
        path,
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": revision,
            "question": question,
        },
    )


def evidence(answer):
    return next(row["data"] for row in answer["evidence"] if row["title"] == TITLE)


def test_insights_refresh_after_restart_and_hide_outdated_answer(
    market_client, market_url, market_headers, insight_listing, receipt_evidence, insight_gateway
):
    source = insight_listing()
    receipt_evidence("10.00", days_ago=40)
    receipt_evidence("20.00")
    path = conversation(market_client, market_headers, source)
    first = turn(market_client, market_headers, path, 0, "Where can I improve profit?")
    assert first.status_code == 200
    assert evidence(first.json()["answer"])["receipts"]["difference"]["change"] == "10.000000"
    receipt_evidence("5.00")
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = insight_gateway
        second = turn(restarted, market_headers, path, 1, "Why is that only a review opportunity?")
        assert second.status_code == 200
        assert second.json()["context_turns"] == 1
        assert evidence(second.json()["answer"])["receipts"]["current"]["recorded_total"] == "25.00"
        history = restarted.get(path, headers=market_headers).json()["items"]
        assert history[0]["answer"] is None
        assert history[0]["answer_status"] == "evidence_changed"
        assert history[1]["answer_status"] == "available"
    prompt = json.dumps(insight_gateway.calls)
    assert "PRIVATE_RECEIPT" not in prompt
    assert "PRIVATE_PRODUCTION" not in prompt
    assert "PRIVATE_RECEIPT" not in second.text
    model_facts = json.loads(insight_gateway.calls[-1][-1]["content"])["EVIDENCE"]
    projected = next(row["data"] for row in model_facts if row["title"] == TITLE)
    assert "pricing" not in projected and "receipts" not in projected
    assert projected["receipt_baseline_available"] is True


def test_changing_receipts_during_inference_refuses_to_save_stale_insight(
    market_client, market_headers, insight_listing, receipt_evidence, insight_gateway
):
    source = insight_listing()
    path = conversation(market_client, market_headers, source)
    insight_gateway.after = lambda: receipt_evidence("5.00")
    response = turn(market_client, market_headers, path, 0, "Review recorded opportunities.")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ASSISTANT_EVIDENCE_CHANGED"
    assert market_client.get(path, headers=market_headers).json()["items"] == []


def test_logout_during_insight_inference_refuses_answer(
    market_client, market_headers, insight_listing, insight_gateway
):
    source = insight_listing()
    path = conversation(market_client, market_headers, source)
    insight_gateway.after = lambda: market_client.post(
        "/api/v1/auth/logout", headers=market_headers
    )
    response = turn(market_client, market_headers, path, 0, "Review recorded opportunities.")
    assert response.status_code == 401
    assert "answer" not in response.json()


def test_buyer_cannot_request_private_insights(
    market_client, buyer_headers, insight_listing, insight_gateway
):
    source = insight_listing()
    response = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "listing_ids": [source["listing"]["id"]],
            "question": "Show private profit opportunities.",
            "insights": {},
        },
    )
    assert response.status_code == 422
    assert insight_gateway.calls == []


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local Qwen insight dialogue evaluation is opt-in.",
)
def test_local_insight_two_turn_dialogue(market_client, market_headers, insight_listing):
    from fairmade.assistants.gateway import OllamaGateway

    market_client.app.state.assistant_gateway = OllamaGateway()
    source = insight_listing()
    path = conversation(market_client, market_headers, source)
    for revision, question in enumerate(
        ["Explain my price warning without changing quality.", "Why is that a modeled warning?"]
    ):
        response = turn(market_client, market_headers, path, revision, question)
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
        answer = response.json()["answer"]
        assert evidence(answer)["pricing"]["below_break_even"] is True
        assert answer["paragraphs"] and answer["facts"]
