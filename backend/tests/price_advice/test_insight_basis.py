"""A combined explanation uses one selected economic basis across reports."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from fairmade.cost_calendar.integration import TITLE as CALENDAR_TITLE
from fairmade.main import create_app
from fairmade.seller_insights.integration import TITLE as INSIGHT_TITLE


def newer_analysis(client, headers, source, payload):
    changed = deepcopy(payload)
    changed["costs"][0]["amount"] = "999"
    response = client.post(source["path"] + "/analyses", headers=headers, json=changed)
    assert response.status_code == 201
    return response.json()


def assert_selected_basis(answer, selected_id):
    evidence = {item["title"]: item["data"] for item in answer["evidence"]}
    assert evidence["Selected saved production economics"]["analysis_id"] == selected_id
    assert evidence[INSIGHT_TITLE]["pricing"]["analysis_id"] == selected_id
    assert evidence[CALENDAR_TITLE]["seasonality_status"] == "not_established"


@pytest.mark.parametrize("selection", ["review", "explicit", "latest"])
def test_stateless_insights_use_the_selected_economic_basis(
    market_client, market_headers, advice_source, payload, advice_gateway, selection
):
    source = advice_source()
    newest = newer_analysis(market_client, market_headers, source, payload)
    body = {
        "product_id": source["product"]["id"],
        "question": "Explain the current evidence and its limitations.",
        "insights": {"period_days": 30},
        "cost_calendar": {"months": 24},
    }
    selected = source["analysis"]["id"]
    if selection == "review":
        body["pricing_review_id"] = source["advice_review"]["id"]
    elif selection == "explicit":
        body["analysis_id"] = selected
    else:
        selected = newest["id"]
    # The test gateway cites price advice; retain that when testing default/explicit selection.
    if selection != "review":

        def complete(messages, schema):
            if "proposed_prices" in schema["properties"]:
                return {"proposed_prices": []}
            facts = json.loads(messages[-1]["content"])["EVIDENCE"]
            key = next(item["key"] for item in facts if item["title"] == INSIGHT_TITLE)
            return {"paragraphs": [{"text": "Review recorded evidence.", "evidence_keys": [key]}]}

        advice_gateway.complete = complete
    response = market_client.post("/api/v1/assistants/seller", headers=market_headers, json=body)
    assert response.status_code == 200, response.text
    assert_selected_basis(response.json(), selected)


def test_saved_combined_scope_retains_review_basis_across_restart(
    market_client, market_url, market_headers, advice_source, payload, advice_gateway
):
    source = advice_source()
    newer_analysis(market_client, market_headers, source, payload)
    scope = {
        "role": "seller",
        "product_id": source["product"]["id"],
        "pricing_review_id": source["advice_review"]["id"],
        "insights": {"period_days": 30},
        "cost_calendar": {"months": 24},
    }
    created = market_client.post(
        "/api/v1/assistants/conversations",
        headers=market_headers,
        json={"request_id": str(uuid4()), "scope": scope},
    )
    assert created.status_code == 201, created.text
    path = "/api/v1/assistants/conversations/" + created.json()["id"] + "/turns"
    for revision in range(2):
        with TestClient(create_app(market_url)) as restarted:
            restarted.app.state.assistant_gateway = advice_gateway
            response = restarted.post(
                path,
                headers=market_headers,
                json={
                    "request_id": str(uuid4()),
                    "expected_revision": revision,
                    "question": "Explain the current evidence and its limitations.",
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["context_turns"] == revision
            assert_selected_basis(response.json()["answer"], source["analysis"]["id"])
            model = json.loads(advice_gateway.calls[-1][-1]["content"])["EVIDENCE"]
            for item in model:
                if item["title"] in (INSIGHT_TITLE, CALENDAR_TITLE):
                    assert "unit_cost" not in json.dumps(item["data"])
