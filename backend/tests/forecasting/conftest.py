import json
from datetime import datetime, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import Order, PayPalCheckout, Product


class ForecastGateway:
    def __init__(self):
        self.calls = []
        self.after = None

    def complete(self, messages, schema):
        self.calls.append(messages)
        if "proposed_prices" in schema["properties"]:
            return {"proposed_prices": []}
        if self.after:
            self.after()
        facts = json.loads(messages[-1]["content"])["EVIDENCE"]
        return {
            "paragraphs": [
                {
                    "text": "Treat the observed baseline as conditional; review missing history.",
                    "evidence_keys": [facts[-1]["key"]],
                }
            ]
        }


@pytest.fixture
def forecast_gateway(market_client):
    gateway = ForecastGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def forecast_path(order_source):
    return order_source["path"] + "/forecasts"


@pytest.fixture
def verified_sales(paypal_client, buyer_headers, order_source, fake_gateway):
    today = utcnow().date()
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.get(Product, order_source["product"]["id"]).created_at = datetime.combine(
            today - timedelta(days=60), time(1)
        )

    def create(days=(2, 4, 7), quantity=3):
        ids = []
        for days_ago in days:
            created = paypal_client.post(
                "/api/v1/orders",
                headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
                json={
                    "items": [
                        {
                            "listing_id": order_source["listing"]["id"],
                            "expected_listing_revision": 1,
                            "quantity": quantity,
                        }
                    ]
                },
            )
            assert created.status_code == 201, created.text
            order_id = created.json()["id"]
            path = "/api/v1/orders/" + order_id + "/paypal-checkout"
            checkout = paypal_client.post(path, headers=buyer_headers, json={})
            assert checkout.status_code == 200, checkout.text
            with Session(paypal_client.app.state.engine) as db:
                provider_id = db.get(PayPalCheckout, order_id).provider_order_id
            fake_gateway.approve(provider_id)
            capture = paypal_client.post(path + "/capture", headers=buyer_headers, json={})
            assert capture.status_code == 200, capture.text
            ordered = datetime.combine(today - timedelta(days=days_ago), time(12))
            with Session(paypal_client.app.state.engine) as db, db.begin():
                order = db.get(Order, order_id)
                order.created_at = ordered
                order.expires_at = ordered + timedelta(minutes=15)
                db.get(PayPalCheckout, order_id).verified_at = ordered + timedelta(minutes=1)
            ids.append(order_id)
        return ids

    return create
