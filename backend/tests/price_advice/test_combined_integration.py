"""Local integration checks across separately published assistant extensions."""

import json
from copy import deepcopy
from uuid import uuid4

from fastapi.testclient import TestClient

from fairmade.composition.integration import TITLE as RECIPE_TITLE
from fairmade.cost_calendar.integration import TITLE as CALENDAR_TITLE
from fairmade.forecasting.integration import TITLE as FORECAST_TITLE
from fairmade.main import create_app
from fairmade.price_advice.integration import TITLE as ADVICE_TITLE
from fairmade.seller_insights.integration import TITLE as INSIGHT_TITLE


def test_combined_saved_scope_keeps_selected_economics_and_qualitative_projections(
    market_client, market_url, market_headers, advice_source, payload, advice_gateway
):
    source = advice_source()
    changed = deepcopy(payload)
    changed["costs"][0]["amount"] = "999"
    newest = market_client.post(source["path"] + "/analyses", headers=market_headers, json=changed)
    assert newest.status_code == 201
    scope = {
        "role": "seller",
        "product_id": source["product"]["id"],
        "pricing_review_id": source["advice_review"]["id"],
        "insights": {"period_days": 30},
        "cost_calendar": {"months": 24},
        "forecast": {"lookback_days": 30, "horizon_days": 7},
        "include_recipe_inputs": True,
    }
    created = market_client.post(
        "/api/v1/assistants/conversations",
        headers=market_headers,
        json={"request_id": str(uuid4()), "scope": scope},
    )
    assert created.status_code == 201, created.text
    path = "/api/v1/assistants/conversations/" + created.json()["id"]
    assert {
        key: value for key, value in created.json()["scope"].items() if value is not None
    } == scope
    for revision in range(2):
        with TestClient(create_app(market_url)) as restarted:
            restarted.app.state.assistant_gateway = advice_gateway
            response = restarted.post(
                path + "/turns",
                headers=market_headers,
                json={
                    "request_id": str(uuid4()),
                    "expected_revision": revision,
                    "question": "Explain the current evidence and its limitations.",
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["context_turns"] == revision
            facts = {item["title"]: item["data"] for item in response.json()["answer"]["evidence"]}
            assert facts[ADVICE_TITLE]["pricing_analysis_id"] == source["analysis"]["id"]
            assert facts[INSIGHT_TITLE]["pricing"]["analysis_id"] == source["analysis"]["id"]
            assert facts[CALENDAR_TITLE]["seasonality_status"] == "not_established"
            assert facts[RECIPE_TITLE]["status"] == "missing_recipe"
            assert facts[FORECAST_TITLE]["status"] == "insufficient_history"
            model = {
                item["title"]: item["data"]
                for item in json.loads(advice_gateway.calls[-1][-1]["content"])["EVIDENCE"]
            }
            for title in (ADVICE_TITLE, INSIGHT_TITLE, CALENDAR_TITLE, FORECAST_TITLE):
                assert "unit_cost" not in json.dumps(model[title])
                assert "999" not in json.dumps(model[title])
            history = restarted.get(path + "/turns", headers=market_headers).json()["items"]
            assert len(history) == revision + 1
