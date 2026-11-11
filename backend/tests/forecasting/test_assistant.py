import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AccountRole, SellableInventory


def request(order_source):
    return {
        "question": "Explain my sales forecast and inventory planning limitations.",
        "product_id": order_source["product"]["id"],
        "forecast": {"lookback_days": 28, "horizon_days": 7},
    }


def test_grounded_forecast_facts_and_private_qualitative_context(
    paypal_client,
    market_headers,
    order_source,
    verified_sales,
    forecast_gateway,
):
    verified_sales()
    response = paypal_client.post(
        "/api/v1/assistants/seller", headers=market_headers, json=request(order_source)
    )
    assert response.status_code == 200, response.text
    facts = response.json()["facts"]
    assert any("2.250000" in fact["text"] for fact in facts)
    assert any("additional whole selling units" in fact["text"] for fact in facts)
    data = json.loads(forecast_gateway.calls[-1][-1]["content"])
    forecast = next(fact for fact in data["EVIDENCE"] if "observed sales baseline" in fact["title"])
    assert forecast["data"]["status"] == "baseline_available"
    assert forecast["data"]["additional_units_indicated"] is True
    text = json.dumps(data["EVIDENCE"])
    assert "captured_at" not in text and "order_id" not in text and "capture_id" not in text
    assert "2.250000" not in text
    assert "PRIVATE_PAYER" not in text and "PRIVATE_MERCHANT" not in text
    assert response.headers["cache-control"] == "no-store"


def test_sparse_history_explanation_never_returns_numeric_projection(
    market_client,
    market_headers,
    order_source,
    forecast_gateway,
):
    response = market_client.post(
        "/api/v1/assistants/seller", headers=market_headers, json=request(order_source)
    )
    assert response.status_code == 200, response.text
    assert any("Insufficient recorded history" in fact["text"] for fact in response.json()["facts"])
    forecast = next(
        fact for fact in response.json()["evidence"] if "observed sales baseline" in fact["title"]
    )
    assert forecast["data"]["projected_units"] is None


def test_saved_forecast_follow_up_survives_restart_and_rechecks_stock(
    paypal_client,
    market_url,
    market_headers,
    market_account,
    order_source,
    verified_sales,
    forecast_gateway,
):
    verified_sales()
    created = paypal_client.post(
        "/api/v1/assistants/conversations",
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {
                "role": "seller",
                "product_id": order_source["product"]["id"],
                "forecast": {},
            },
        },
    )
    assert created.status_code == 201, created.text
    path = "/api/v1/assistants/conversations/" + created.json()["id"]
    first = paypal_client.post(
        path + "/turns",
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": 0,
            "question": "Explain my product's forecast.",
        },
    )
    assert first.status_code == 200, first.text
    app = create_app(market_url)
    app.state.assistant_gateway = forecast_gateway
    with TestClient(app) as restarted:
        second = restarted.post(
            path + "/turns",
            headers=market_headers,
            json={
                "request_id": str(uuid4()),
                "expected_revision": 1,
                "question": "Why should I treat that cautiously?",
            },
        )
        assert second.status_code == 200, second.text
        assert second.json()["context_turns"] == 1
        assert any(message["role"] == "assistant" for message in forecast_gateway.calls[-1][1:-1])
        with Session(app.state.engine) as db, db.begin():
            db.execute(update(SellableInventory).values(on_hand=20))
        history = restarted.get(path + "/turns", headers=market_headers)
        assert history.status_code == 200
        assert all(row["answer"] is None for row in history.json()["items"])
        other = market_account("other-forecast-chat@example.com")
        assert restarted.get(path, headers=other).status_code == 404
        erased = restarted.delete(path, headers=market_headers)
        assert erased.status_code == 204


@pytest.mark.parametrize("change", ["stock", "logout", "role"])
def test_state_changes_during_inference_invalidate_answer(
    paypal_client,
    market_headers,
    order_source,
    verified_sales,
    forecast_gateway,
    change,
):
    verified_sales()

    def mutate():
        if change == "stock":
            with Session(paypal_client.app.state.engine) as db, db.begin():
                db.execute(update(SellableInventory).values(on_hand=20))
        elif change == "logout":
            paypal_client.post("/api/v1/auth/logout", headers=market_headers)
        else:
            from sqlalchemy import delete

            with Session(paypal_client.app.state.engine) as db, db.begin():
                db.execute(delete(AccountRole).where(AccountRole.role == "seller"))

    forecast_gateway.after = mutate
    response = paypal_client.post(
        "/api/v1/assistants/seller", headers=market_headers, json=request(order_source)
    )
    assert response.status_code == {"stock": 409, "logout": 401, "role": 403}[change], response.text
