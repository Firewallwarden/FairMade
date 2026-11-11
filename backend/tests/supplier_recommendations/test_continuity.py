import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from fairmade.main import create_app
from fairmade.supplier_recommendations.integration import TITLE


def conversation(client, headers, source, options):
    response = client.post(
        "/api/v1/assistants/conversations",
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "scope": {
                "role": "seller",
                "product_id": source["product"]["id"],
                "supplier_report_id": source["report"]["id"],
                "recommendations": options,
            },
        },
    )
    assert response.status_code == 201, response.text
    return "/api/v1/assistants/conversations/" + response.json()["id"] + "/turns"


def ask(client, headers, path, revision, question="Explain the selected supplier tradeoff."):
    return client.post(
        path,
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": revision,
            "question": question,
        },
    )


def options(body):
    return {key: value for key, value in body.items() if key != "supplier_report_id"}


def test_saved_modes_survive_restart_and_model_never_receives_private_notes(
    market_client, market_url, market_headers, supplier_body, recommendation_gateway
):
    source, body = supplier_body
    path = conversation(market_client, market_headers, source, options(body))
    first = ask(market_client, market_headers, path, 0)
    assert first.status_code == 200, first.text
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = recommendation_gateway
        second = ask(restarted, market_headers, path, 1, "Why is that not automatic approval?")
        assert second.status_code == 200, second.text
        assert second.json()["context_turns"] == 1
        report = next(
            row["data"] for row in second.json()["answer"]["evidence"] if row["title"] == TITLE
        )
        assert set(report["selected_quote_ids"]) == set(source["ids"][:2])
    assert "PRIVATE_SUPPLIER_NOTES" not in json.dumps(recommendation_gateway.calls)
    model = json.loads(recommendation_gateway.calls[-1][-1]["content"])["EVIDENCE"]
    context = next(row["data"] for row in model if row["title"] == TITLE)
    assert "objective_cost" not in json.dumps(context)
    assert "purchase_cost" not in json.dumps(context)
    assert any(not row["eligible"] for row in context["candidates"])


def update_locks(client, headers, source):
    response = client.put(
        source["supplier_path"] + "/quality-locks",
        headers=headers,
        json={
            "expected_revision": 1,
            "rules": [
                {
                    "key": "new_requirement",
                    "label": "Additional requirement",
                    "type": "boolean",
                    "expected": True,
                }
            ],
        },
    )
    assert response.status_code == 200


def test_followup_rechecks_current_requirements_and_hides_previous_selection(
    market_client, market_headers, supplier_body, recommendation_gateway
):
    source, body = supplier_body
    path = conversation(market_client, market_headers, source, options(body))
    assert ask(market_client, market_headers, path, 0).status_code == 200
    update_locks(market_client, market_headers, source)
    second = ask(market_client, market_headers, path, 1, "Which quotes are eligible now?")
    assert second.status_code == 200, second.text
    data = next(row["data"] for row in second.json()["answer"]["evidence"] if row["title"] == TITLE)
    assert data["selected_quote_ids"] == [] and data["rule_revision"] == 2
    history = market_client.get(path, headers=market_headers).json()["items"]
    assert history[0]["answer_status"] == "evidence_changed" and history[0]["answer"] is None


@pytest.mark.parametrize("change,expected", [("locks", 409), ("logout", 401)])
def test_inference_races_cannot_save_stale_recommendation(
    market_client, market_headers, supplier_body, recommendation_gateway, change, expected
):
    source, body = supplier_body
    path = conversation(market_client, market_headers, source, options(body))
    recommendation_gateway.after = (
        (lambda: update_locks(market_client, market_headers, source))
        if change == "locks"
        else lambda: market_client.post("/api/v1/auth/logout", headers=market_headers)
    )
    response = ask(market_client, market_headers, path, 0)
    assert response.status_code == expected, response.text
    if change == "locks":
        assert market_client.get(path, headers=market_headers).json()["items"] == []


def test_seller_options_need_a_report_and_buyer_cannot_request_them(
    market_client, market_headers, buyer_headers, supplier_body, recommendation_gateway
):
    source, body = supplier_body
    result = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            "question": "Explain.",
            "product_id": source["product"]["id"],
            "recommendations": options(body),
        },
    )
    assert result.status_code == 422
    result = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "question": "Show private recommendations.",
            "listing_ids": [str(uuid4())],
            "recommendations": options(body),
        },
    )
    assert result.status_code == 422 and recommendation_gateway.calls == []


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Local supplier mode eval is opt-in.",
)
def test_real_local_supplier_mode_followup(market_client, market_headers, supplier_body):
    from fairmade.assistants.gateway import OllamaGateway

    market_client.app.state.assistant_gateway = OllamaGateway()
    source, body = supplier_body
    path = conversation(market_client, market_headers, source, options(body))
    for revision, question in enumerate(
        [
            "Explain the balanced supplier review without approving a substitution.",
            "Why does that not establish certified quality?",
        ]
    ):
        response = ask(market_client, market_headers, path, revision, question)
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
        assert any(row["title"] == TITLE for row in response.json()["answer"]["evidence"])
