from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.models import Order, Product, SellableInventory


def test_verified_product_units_and_known_stock_are_read_only(
    paypal_client,
    market_headers,
    forecast_path,
    verified_sales,
):
    ids = verified_sales()
    with Session(paypal_client.app.state.engine) as db:
        original_stock = db.scalar(select(SellableInventory.on_hand))
        original_orders = len(db.scalars(select(Order)).all())
    response = paypal_client.post(forecast_path, headers=market_headers, json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "baseline_available"
    assert body["history"]["units"] == 9 and body["history"]["sale_dates"] == 3
    assert body["projected_units"] == "2.250000"
    assert body["inventory"]["additional_whole_units"] == 2
    assert body["inventory"]["available_units"] == 1
    assert response.headers["cache-control"] == "no-store"
    assert not any(identifier in response.text for identifier in ids)
    assert "PRIVATE_" not in response.text
    assert "provider" not in response.text.lower()
    with Session(paypal_client.app.state.engine) as db:
        assert db.scalar(select(SellableInventory.on_hand)) == original_stock
        assert len(db.scalars(select(Order)).all()) == original_orders


def test_new_or_sparse_product_has_no_forecast(market_client, market_headers, forecast_path):
    response = market_client.post(forecast_path, headers=market_headers, json={})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "insufficient_history"
    assert response.json()["projected_units"] is None
    assert response.json()["inventory"]["additional_whole_units"] is None


def test_capture_boundary_includes_start_but_not_partial_today_or_future(
    paypal_client,
    market_headers,
    forecast_path,
    verified_sales,
):
    verified_sales(days=(28, 27, 26, 29, 0, -1), quantity=1)
    response = paypal_client.post(forecast_path, headers=market_headers, json={})
    assert response.status_code == 200, response.text
    assert response.json()["history"]["units"] == 3
    assert response.json()["history"]["sale_dates"] == 3


def test_pending_or_unverified_orders_do_not_create_observations(
    paypal_client,
    buyer_headers,
    market_headers,
    forecast_path,
    checkout,
    verified_sales,
):
    response = paypal_client.post(forecast_path, headers=market_headers, json={})
    assert response.status_code == 200
    assert response.json()["history"]["units"] == 0
    assert response.json()["status"] == "insufficient_history"


def test_historical_basis_is_not_replaced_with_current_unit(
    paypal_client,
    market_headers,
    forecast_path,
    verified_sales,
    order_source,
):
    verified_sales()
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.get(Product, order_source["product"]["id"]).selling_unit = "item"
    response = paypal_client.post(forecast_path, headers=market_headers, json={})
    assert response.status_code == 200
    body = response.json()
    assert body["history"]["excluded_basis_lines"] == 3
    assert body["history"]["units"] == 0
    assert body["inventory"]["status"] == "unknown"


def test_missing_historical_basis_preserves_unknown(
    paypal_client,
    market_headers,
    forecast_path,
    verified_sales,
):
    ids = verified_sales()
    with Session(paypal_client.app.state.engine) as db, db.begin():
        row = db.get(Order, ids[0])
        snapshot = deepcopy(row.snapshot)
        snapshot["items"][0]["listing"]["product"].pop("selling_unit")
        row.snapshot = snapshot
    body = paypal_client.post(forecast_path, headers=market_headers, json={}).json()
    assert body["history"]["excluded_basis_lines"] == 1
    assert body["history"]["units"] == 6
    assert body["status"] == "insufficient_history"


def test_complete_query_is_bounded_without_silent_sample_truncation(
    paypal_client,
    market_headers,
    forecast_path,
    verified_sales,
    monkeypatch,
):
    import fairmade.forecasting.repository as repository

    verified_sales()
    monkeypatch.setattr(repository, "MAX_LINES", 2)
    response = paypal_client.post(forecast_path, headers=market_headers, json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "FORECAST_SCOPE_TOO_LARGE"


def test_refund_request_excludes_order_from_baseline(
    paypal_client,
    buyer_headers,
    market_headers,
    forecast_path,
    verified_sales,
):
    identifier = verified_sales()[0]
    request = paypal_client.post(
        "/api/v1/orders/" + identifier + "/refund-request",
        headers=buyer_headers,
        json={"reason": "Synthetic buyer refund request."},
    )
    assert request.status_code == 201, request.text
    response = paypal_client.post(forecast_path, headers=market_headers, json={})
    assert response.status_code == 200
    body = response.json()
    assert body["history"]["units"] == 6
    assert body["history"]["excluded_refund_lines"] == 1
    assert body["status"] == "insufficient_history"


def test_owner_role_and_auth_boundaries(
    market_client, market_headers, buyer_headers, market_account, forecast_path
):
    assert market_client.post(forecast_path, json={}).status_code == 401
    assert market_client.post(forecast_path, headers=buyer_headers, json={}).status_code == 403
    other = market_account("other-forecast-seller@example.com")
    response = market_client.post(forecast_path, headers=other, json={})
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert (
        market_client.post(
            "/api/v1/products/" + str(uuid4()) + "/forecasts", headers=market_headers, json={}
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "body",
    [
        {"lookback_days": True},
        {"lookback_days": "28"},
        {"lookback_days": 13},
        {"lookback_days": 91},
        {"horizon_days": 0},
        {"horizon_days": 31},
        {"horizon_days": 1.5},
        {"offline_sales": "PRIVATE_OFFLINE_RECORD"},
        {"as_of_date": "2026-01-01"},
        {"daily_rate": "PRIVATE_GUESSED_RATE"},
    ],
)
def test_strict_windows_and_no_invented_or_offline_inputs(
    market_client,
    market_headers,
    forecast_path,
    body,
):
    response = market_client.post(forecast_path, headers=market_headers, json=body)
    assert response.status_code == 422
    assert "PRIVATE_" not in response.text
    assert response.headers["cache-control"] == "no-store"
