import json
import os
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from fairmade.main import create_app
from fairmade.price_advice.integration import TITLE


def conversation(client, headers, source):
    response = client.post(
        "/api/v1/assistants/conversations",
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "scope": {
                "role": "seller",
                "product_id": source["product"]["id"],
                "pricing_review_id": source["advice_review"]["id"],
            },
        },
    )
    assert response.status_code == 201, response.text
    return "/api/v1/assistants/conversations/" + response.json()["id"] + "/turns"


def ask(client, headers, path, revision, question="Explain why the review range is conditional."):
    return client.post(
        path,
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": revision,
            "question": question,
        },
    )


def report(answer):
    return next(fact["data"] for fact in answer["evidence"] if fact["title"] == TITLE)


def change_locks(client, headers, source):
    response = client.put(
        source["path"] + "/quality-locks",
        headers=headers,
        json={
            "expected_revision": 1,
            "rules": [
                {
                    "key": "new_requirement",
                    "label": "New requirement",
                    "type": "boolean",
                    "expected": True,
                }
            ],
        },
    )
    assert response.status_code == 200


def test_review_pins_analysis_and_requested_scenarios_instead_of_using_latest_costs(
    market_client, market_headers, advice_source, payload, advice_gateway
):
    source = advice_source()
    changed = deepcopy(payload)
    changed["costs"][0]["amount"] = "999"
    newest = market_client.post(source["path"] + "/analyses", headers=market_headers, json=changed)
    assert newest.status_code == 201
    advice_gateway.prices = ["8"]
    body = {
        "product_id": source["product"]["id"],
        "pricing_review_id": source["advice_review"]["id"],
        "question": "What if I charge $8?",
    }
    response = market_client.post("/api/v1/assistants/seller", headers=market_headers, json=body)
    assert response.status_code == 200, response.text
    selected = report(response.json())
    assert selected["pricing_analysis_id"] == source["analysis"]["id"]
    scenarios = next(
        row
        for row in response.json()["evidence"]
        if row["title"] == "Deterministic requested price scenarios"
    )
    assert scenarios["data"]["analysis_id"] == source["analysis"]["id"]
    advice_gateway.calls.clear()
    mismatch = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={**body, "analysis_id": newest.json()["id"]},
    )
    assert mismatch.status_code == 409 and advice_gateway.calls == []
    assert mismatch.json()["detail"]["code"] == "PRICING_SOURCE_MISMATCH"


def test_saved_advice_continuity_after_restart_and_private_projection(
    market_client, market_url, market_headers, advice_source, advice_gateway
):
    source = advice_source()
    path = conversation(market_client, market_headers, source)
    first = ask(market_client, market_headers, path, 0)
    assert first.status_code == 200
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = advice_gateway
        response = ask(restarted, market_headers, path, 1, "Why does that not establish fairness?")
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == 1
        assert report(response.json()["answer"])["status"] == "conditional_overlap"
    assert "PRIVATE_COMPARATOR" not in json.dumps(advice_gateway.calls)
    model_facts = json.loads(advice_gateway.calls[-1][-1]["content"])["EVIDENCE"]
    context = next(fact["data"] for fact in model_facts if fact["title"] == TITLE)
    assert context["recommendation_available"] is True
    assert "recommended_review_range" not in context and "market_sources" not in context


def test_new_requirements_block_followup_and_hide_prior_advice(
    market_client, market_headers, advice_source, advice_gateway
):
    source = advice_source()
    path = conversation(market_client, market_headers, source)
    assert ask(market_client, market_headers, path, 0).status_code == 200
    change_locks(market_client, market_headers, source)
    response = ask(market_client, market_headers, path, 1, "What does the current evidence permit?")
    assert response.status_code == 200, response.text
    assert report(response.json()["answer"])["recommended_review_range"] is None
    assert report(response.json()["answer"])["status"] == "quality_blocked"
    history = market_client.get(path, headers=market_headers).json()["items"]
    assert history[0]["answer"] is None and history[0]["answer_status"] == "evidence_changed"


@pytest.mark.parametrize("change,expected", [("locks", 409), ("logout", 401)])
def test_inference_time_changes_refuse_stale_price_advice(
    market_client, market_headers, advice_source, advice_gateway, change, expected
):
    source = advice_source()
    path = conversation(market_client, market_headers, source)
    advice_gateway.after = (
        (lambda: change_locks(market_client, market_headers, source))
        if change == "locks"
        else lambda: market_client.post("/api/v1/auth/logout", headers=market_headers)
    )
    response = ask(market_client, market_headers, path, 0)
    assert response.status_code == expected
    if change == "locks":
        assert market_client.get(path, headers=market_headers).json()["items"] == []


def test_buyer_cannot_request_private_pricing_review(
    market_client, buyer_headers, advice_source, advice_gateway
):
    source = advice_source()
    response = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "listing_ids": [str(uuid4())],
            "pricing_review_id": source["advice_review"]["id"],
            "question": "Show private pricing advice.",
        },
    )
    assert response.status_code == 422 and advice_gateway.calls == []


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Local price advice evaluation is opt-in.",
)
def test_real_local_price_advice_dialogue(market_client, market_headers, advice_source):
    from fairmade.assistants.gateway import OllamaGateway

    market_client.app.state.assistant_gateway = OllamaGateway()
    source = advice_source()
    path = conversation(market_client, market_headers, source)
    for revision, question in enumerate(
        [
            "Explain the conditional price range and its evidence limits.",
            "Why does that not prove an objectively fair price?",
        ]
    ):
        response = ask(market_client, market_headers, path, revision, question)
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
        assert report(response.json()["answer"])["status"] == "conditional_overlap"
