from datetime import UTC, datetime
from decimal import Decimal, localcontext

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from fairmade.assistants.history import cost_history, period_for
from fairmade.assistants.schemas import HistoryPeriod, SellerQuestion
from fairmade.models import Analysis, OrderSalesCostSnapshot, PayPalCheckout

PERIOD = {"start_date": "2026-01-01", "end_date": "2026-02-01"}


@pytest.mark.parametrize(
    "question,start,end",
    [
        ("Sales last month?", "2026-01-01", "2026-02-01"),
        ("Sales this month?", "2026-02-01", "2026-02-16"),
        ("Sales last 7 days?", "2026-02-09", "2026-02-16"),
        ("Revenue last week?", "2026-02-09", "2026-02-16"),
        ("Sales yesterday?", "2026-02-14", "2026-02-15"),
        ("Cost history today?", "2026-02-15", "2026-02-16"),
        ("Sales last year?", "2025-01-01", "2026-01-01"),
        ("Why have costs increased?", "2026-01-17", "2026-02-16"),
    ],
)
def test_utc_relative_periods(monkeypatch, question, start, end):
    monkeypatch.setattr(
        "fairmade.assistants.history.utcnow", lambda: datetime(2026, 2, 15, tzinfo=UTC)
    )
    body = SellerQuestion(question=question, product_id="11111111-1111-4111-8111-111111111111")
    assert period_for(body).model_dump(mode="json") == {"start_date": start, "end_date": end}


@pytest.mark.parametrize(
    "question", ["Sales last 999 days?", "Sales in 2025?", "Sales last quarter?"]
)
def test_ambiguous_or_unbounded_periods_require_explicit_scope(question):
    body = SellerQuestion(question=question, product_id="11111111-1111-4111-8111-111111111111")
    with pytest.raises(HTTPException) as exc:
        period_for(body)
    assert exc.value.status_code == 422


def test_cost_history_normalizes_yields_and_does_not_invent_causation(
    market_client,
    market_headers,
    market_record,
    payload,
):
    with Session(market_client.app.state.engine) as db, db.begin():
        db.get(Analysis, market_record["analysis"]["id"]).created_at = datetime(2026, 1, 1)
    payload["sellable_units"] = 20
    payload["costs"][0]["amount"] = "100.00"
    created = market_client.post(
        market_record["path"] + "/analyses", headers=market_headers, json=payload
    )
    assert created.status_code == 201
    with Session(market_client.app.state.engine) as db, db.begin():
        db.get(Analysis, created.json()["id"]).created_at = datetime(2026, 1, 2)
    with Session(market_client.app.state.engine) as db, localcontext() as context:
        context.prec = 2
        result = cost_history(db, market_record["product"]["id"], HistoryPeriod(**PERIOD))
    assert result["nominal_basis_comparable"] is True
    assert Decimal(result["latest_minus_earliest_unit_cost"]) == Decimal("-2.5")
    assert Decimal(result["component_changes_per_unit"]["materials"]) == 0
    assert Decimal(result["component_changes_per_unit"]["labor"]) == Decimal("-1.5")
    assert "not observed expense dates" in result["limitations"][0]


def test_incompatible_units_do_not_produce_a_cost_trend(
    market_client,
    market_headers,
    market_record,
    payload,
):
    market_client.patch(market_record["path"], headers=market_headers, json={"selling_unit": "box"})
    second = market_client.post(
        market_record["path"] + "/analyses", headers=market_headers, json=payload
    )
    assert second.status_code == 201
    with Session(market_client.app.state.engine) as db, db.begin():
        for identifier in (market_record["analysis"]["id"], second.json()["id"]):
            db.get(Analysis, identifier).created_at = datetime(2026, 1, 2)
    with Session(market_client.app.state.engine) as db:
        result = cost_history(db, market_record["product"]["id"], HistoryPeriod(**PERIOD))
    assert result["nominal_basis_comparable"] is False
    assert result["latest_minus_earliest_unit_cost"] is None


def test_history_is_additive_owner_scoped_and_stable_during_inference(
    market_client,
    market_headers,
    seller_question,
    ai_gateway,
):
    result = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "question": "Summarize sales and cost history.",
            "history_period": PERIOD,
        },
    )
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["evidence"][-2]["data"]["sales_count"] == 0
    assert data["evidence"][-1]["data"]["observations"] == []
    assert any("Seller-wide sandbox captures" in fact["text"] for fact in data["facts"])
    assert result.headers["Cache-Control"] == "no-store"


@pytest.fixture
def selected_history_order(market_client, market_headers, order_source, request):
    response = market_client.put(
        order_source["path"] + "/sales-cost-basis",
        headers=market_headers,
        json={
            "expected_revision": 0,
            "analysis_id": order_source["analysis"]["id"],
        },
    )
    assert response.status_code == 200
    return request.getfixturevalue("unpaid_order")


@pytest.fixture
def history_sale(
    selected_history_order, paypal_client, fake_gateway, checkout, checkout_path, buyer_headers
):
    fake_gateway.approve(checkout["provider_order_id"])
    captured = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert captured.status_code == 200
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.get(PayPalCheckout, selected_history_order["id"]).verified_at = datetime(2026, 1, 15)
    return selected_history_order


def test_sales_reuses_frozen_costs_and_preserves_unknown_profit(
    market_client,
    market_headers,
    order_source,
    history_sale,
    ai_gateway,
):
    body = {
        "question": "Explain sales history.",
        "product_id": order_source["product"]["id"],
        "history_period": PERIOD,
    }
    result = market_client.post("/api/v1/assistants/seller", headers=market_headers, json=body)
    assert result.status_code == 200, result.text
    summary = result.json()["evidence"][-2]["data"]
    assert summary["sales_count"] == 1 and summary["estimated_profit"] == "13.00"
    expected = market_client.get(
        "/api/v1/seller/sales?start_date=2026-01-01&end_date=2026-02-01",
        headers=market_headers,
    ).json()
    expected.pop("generated_at")
    assert summary == expected
    assert "PRIVATE_PAYER" not in str(result.json())
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(delete(OrderSalesCostSnapshot))
    missing = market_client.post("/api/v1/assistants/seller", headers=market_headers, json=body)
    assert missing.status_code == 200
    assert missing.json()["evidence"][-2]["data"]["estimated_profit"] is None
    assert any("unavailable" in fact["text"] for fact in missing.json()["facts"])


@pytest.mark.parametrize(
    "period",
    [
        {"start_date": "2026-01-02", "end_date": "2026-01-01"},
        {"start_date": "2024-01-01", "end_date": "2026-01-01"},
    ],
)
def test_history_period_input_validation(
    market_client, market_headers, seller_question, ai_gateway, period
):
    result = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **seller_question,
            "history_period": period,
        },
    )
    assert result.status_code == 422 and ai_gateway.calls == []
