"""Seller-selected estimates and verified synthetic sandbox sales."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from fairmade.models import PayPalCheckout

CAPTURED_AT = datetime(2026, 1, 31, 12, tzinfo=UTC)
PERIOD = "?start_date=2026-01-01&end_date=2026-02-01"


@pytest.fixture
def cost_selection(market_client, market_headers, order_source):
    path = order_source["path"] + "/sales-cost-basis"
    response = market_client.put(
        path,
        headers=market_headers,
        json={"expected_revision": 0, "analysis_id": order_source["analysis"]["id"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def selected_order(cost_selection, unpaid_order):
    return unpaid_order


@pytest.fixture
def captured_sale(
    selected_order,
    paypal_client,
    fake_gateway,
    checkout,
    checkout_path,
    buyer_headers,
):
    fake_gateway.approve(checkout["provider_order_id"])
    response = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert response.status_code == 200, response.text
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.get(PayPalCheckout, selected_order["id"]).verified_at = CAPTURED_AT
    return selected_order
