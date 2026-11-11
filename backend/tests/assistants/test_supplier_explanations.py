import json
import os
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from fairmade.assistants.gateway import OllamaGateway
from fairmade.database import utcnow
from fairmade.models import SourcingInput


@pytest.fixture
def quote_report(market_client, market_headers, market_record):
    path = market_record["path"] + "/sourcing-inputs"
    created = market_client.post(path, headers=market_headers, json={"label": "Flour"})
    assert created.status_code == 201
    identifier = created.json()["id"]
    path += "/" + identifier
    rule = {"key": "organic", "label": "Organic claim", "type": "boolean", "expected": True}
    assert (
        market_client.put(
            path + "/quality-locks",
            headers=market_headers,
            json={
                "expected_revision": 0,
                "rules": [rule],
            },
        ).status_code
        == 200
    )

    def build(overrides=None, duplicate=False):
        template = json.loads(
            (Path(__file__).parents[2] / "examples/suppliers/flour-quote.json").read_text()
        )
        template["observed_on"] = utcnow().date().isoformat()
        template["valid_until"] = None
        choices = [
            template,
            {
                **template,
                "supplier_name": "Excluded cheaper quote",
                "package_price": "8.00",
                **(overrides or {"claims": {"organic": {"type": "boolean", "value": False}}}),
            },
        ]
        if duplicate:
            choices[1] = {**template, "supplier_name": "Equal eligible quote"}
        ids = []
        for body in choices:
            response = market_client.post(
                path + "/supplier-quotes", headers=market_headers, json=body
            )
            assert response.status_code == 201, response.text
            ids.append(response.json()["id"])
        report = market_client.post(
            path + "/supplier-comparisons",
            headers=market_headers,
            json={
                "expected_rule_revision": 1,
                "quote_ids": ids,
                "required_quantity": {"value": "9", "unit": "kg"},
                "max_age_days": 30,
            },
        )
        assert report.status_code == 201, report.text
        return {"report_id": report.json()["id"], "input_id": identifier, "quote_ids": ids}

    return build


@pytest.mark.parametrize(
    "overrides,code",
    [
        (None, "QUALITY_FAILED"),
        ({"claims": {}}, "QUALITY_UNKNOWN"),
        ({"availability": "unavailable"}, "UNAVAILABLE"),
        ({"availability": "unknown"}, "AVAILABILITY_UNKNOWN"),
        ({"transport_cost": None}, "TRANSPORT_COST_UNKNOWN"),
        ({"package_quantity": {"value": "5", "unit": "l"}}, "INCOMPATIBLE_UNITS"),
        ({"maximum_packages": 1}, "INSUFFICIENT_AVAILABLE_PACKAGES"),
    ],
)
def test_exclusion_reasons_are_current_and_never_enter_cost_minima(
    market_client,
    market_headers,
    seller_question,
    ai_gateway,
    quote_report,
    overrides,
    code,
):
    selected = quote_report(overrides)
    response = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "supplier_report_id": selected["report_id"],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["evidence"][-1]["data"]
    assert len(data["eligible"]) == 1
    excluded = data["excluded"][0]
    assert code in excluded["exclusion_reasons"] and excluded["reason_messages"]
    assert excluded["acceptable_saving"] is False and "cost" not in excluded
    assert data["lowest_purchase_quote_ids"] == [selected["quote_ids"][0]]
    assert data["lowest_eligible_purchase_cost"] == "40.00"
    assert data["required_quantity"]["unit"] == "kg"
    assert any("EXCLUDED" in fact["text"] for fact in response.json()["facts"])
    context = json.loads(ai_gateway.calls[-1]["messages"][-1]["content"])["EVIDENCE"][-1]["data"]
    assert "EXCLUDED" in context["excluded_alternatives"][0]["status"]


def test_eligible_ties_are_preserved(
    market_client, market_headers, seller_question, ai_gateway, quote_report
):
    selected = quote_report(duplicate=True)
    response = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "supplier_report_id": selected["report_id"],
        },
    )
    assert response.status_code == 200
    data = response.json()["evidence"][-1]["data"]
    assert data["excluded"] == []
    assert data["lowest_purchase_quote_ids"] == selected["quote_ids"]
    assert data["lowest_usable_cost_quote_ids"] == selected["quote_ids"]


def test_report_cannot_be_attached_to_another_product(
    market_client,
    market_headers,
    seller_question,
    market_source,
    ai_gateway,
    quote_report,
):
    selected = quote_report()
    other = market_source()
    response = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "product_id": other["product"]["id"],
            "analysis_id": other["analysis"]["id"],
            "supplier_report_id": selected["report_id"],
        },
    )
    assert response.status_code == 404 and ai_gateway.calls == []


def test_changed_requirements_during_generation_discard_the_explanation(
    market_client,
    market_headers,
    seller_question,
    ai_gateway,
    quote_report,
):
    selected = quote_report()

    def clear():
        with Session(market_client.app.state.engine) as db, db.begin():
            record = db.get(SourcingInput, selected["input_id"])
            record.rules = []
            record.rule_revision += 1

    ai_gateway.after_answer = clear
    response = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "supplier_report_id": selected["report_id"],
        },
    )
    assert response.status_code == 409 and "evidence" not in response.json()


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local model evaluation is opt-in.",
)
def test_real_failed_alternative_explanation(
    market_client,
    market_headers,
    seller_question,
    quote_report,
):
    selected = quote_report()
    market_client.app.state.assistant_gateway = OllamaGateway()
    response = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "supplier_report_id": selected["report_id"],
            "question": (
                "Why is Excluded cheaper quote not acceptable? Explain the ingredient requirement."
            ),
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["evidence"][-1]["data"]
    assert data["excluded"][0]["acceptable_saving"] is False
    assert any("EXCLUDED" in fact["text"] for fact in response.json()["facts"])
    print("LOCAL_SUPPLIER", response.json()["paragraphs"])
