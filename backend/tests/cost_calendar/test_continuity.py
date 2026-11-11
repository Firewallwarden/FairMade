import json
import os
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from fairmade.cost_calendar.integration import TITLE
from fairmade.main import create_app


def conversation(client, headers, source):
    response = client.post(
        "/api/v1/assistants/conversations",
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "scope": {
                "role": "seller",
                "product_id": source["product"]["id"],
                "cost_calendar": {"months": 24},
            },
        },
    )
    assert response.status_code == 201, response.text
    return "/api/v1/assistants/conversations/" + response.json()["id"] + "/turns"


def ask(client, headers, path, revision, question="Explain the recorded annual cost differences."):
    return client.post(
        path,
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": revision,
            "question": question,
        },
    )


def calendar(answer):
    return next(row["data"] for row in answer["evidence"] if row["title"] == TITLE)


def test_saved_calendar_followups_survive_restart_with_private_projection(
    market_client, market_url, market_headers, calendar_source, seed_calendar, calendar_gateway
):
    seed_calendar(date(2025, 1, 15), "2")
    seed_calendar(date(2026, 1, 15), "4")
    path = conversation(market_client, market_headers, calendar_source)
    first = ask(market_client, market_headers, path, 0)
    assert first.status_code == 200
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = calendar_gateway
        second = ask(restarted, market_headers, path, 1, "Why does that not prove seasonality?")
        assert second.status_code == 200, second.text
        assert second.json()["context_turns"] == 1
        assert calendar(second.json()["answer"])["seasonality_status"] == "not_established"
        assert any("change USD 2.000000" in row["text"] for row in second.json()["answer"]["facts"])
    text = json.dumps(calendar_gateway.calls)
    assert "PRIVATE_CALENDAR_COST_LABEL" not in text
    model = json.loads(calendar_gateway.calls[-1][-1]["content"])["EVIDENCE"]
    context = next(row["data"] for row in model if row["title"] == TITLE)
    assert "unit_cost" not in json.dumps(context)
    assert any(row["modeled_direction"] == "increased" for row in context["year_over_year"])


def test_new_historical_snapshot_refreshes_followup_and_hides_old_answer(
    market_client, market_headers, calendar_source, seed_calendar, calendar_gateway
):
    seed_calendar(date(2025, 1, 15), "2")
    seed_calendar(date(2026, 1, 15), "4")
    path = conversation(market_client, market_headers, calendar_source)
    assert ask(market_client, market_headers, path, 0).status_code == 200
    seed_calendar(date(2026, 1, 20), "5")
    response = ask(market_client, market_headers, path, 1, "What do the current snapshots show?")
    assert response.status_code == 200
    annual = next(
        row
        for row in calendar(response.json()["answer"])["year_over_year"]
        if row["current_month"] == "2026-01"
    )
    assert annual["difference"]["change"] == "3.000000"
    history = market_client.get(path, headers=market_headers).json()["items"]
    assert history[0]["answer"] is None and history[0]["answer_status"] == "evidence_changed"


@pytest.mark.parametrize("change,expected", [("history", 409), ("logout", 401)])
def test_inference_time_changes_refuse_stale_calendar_answer(
    market_client,
    market_headers,
    calendar_source,
    seed_calendar,
    calendar_gateway,
    change,
    expected,
):
    seed_calendar(date(2025, 1, 15), "2")
    path = conversation(market_client, market_headers, calendar_source)
    calendar_gateway.after = (
        (lambda: seed_calendar(date(2026, 1, 15), "4"))
        if change == "history"
        else lambda: market_client.post("/api/v1/auth/logout", headers=market_headers)
    )
    response = ask(market_client, market_headers, path, 0)
    assert response.status_code == expected
    if change == "history":
        assert market_client.get(path, headers=market_headers).json()["items"] == []


def test_buyer_cannot_opt_into_private_cost_history(market_client, buyer_headers, calendar_gateway):
    response = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "listing_ids": [str(uuid4())],
            "question": "Reveal private cost history.",
            "cost_calendar": {"months": 24},
        },
    )
    assert response.status_code == 422 and calendar_gateway.calls == []


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Local calendar evaluation is opt-in.",
)
def test_real_local_calendar_followup(
    market_client, market_headers, calendar_source, seed_calendar
):
    from fairmade.assistants.gateway import OllamaGateway

    market_client.app.state.assistant_gateway = OllamaGateway()
    seed_calendar(date(2025, 1, 15), "2")
    seed_calendar(date(2026, 1, 15), "4")
    path = conversation(market_client, market_headers, calendar_source)
    for revision, question in enumerate(
        [
            "Explain the saved cost calendar and its evidence limits.",
            "Why does that not prove seasonal inflation or future prices?",
        ]
    ):
        response = ask(market_client, market_headers, path, revision, question)
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
        assert calendar(response.json()["answer"])["seasonality_status"] == "not_established"
