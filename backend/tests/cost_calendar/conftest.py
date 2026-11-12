import json
from copy import deepcopy
from datetime import date, datetime, time
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from fairmade.cost_calendar.integration import TITLE
from fairmade.models import Analysis, Product
from fairmade.pricing.schemas import PricingRequest
from fairmade.pricing.service import calculate

AS_OF = date(2026, 11, 11)


class CalendarGateway:
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
        key = next(row["key"] for row in facts if row["title"] == TITLE)
        return {
            "paragraphs": [
                {
                    "text": "Saved snapshots do not establish validated seasonal effects.",
                    "evidence_keys": [key],
                }
            ]
        }


@pytest.fixture(autouse=True)
def fixed_calendar_date(monkeypatch):
    monkeypatch.setattr("fairmade.cost_calendar.service.today", lambda: AS_OF)


@pytest.fixture
def calendar_gateway(market_client):
    gateway = CalendarGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def calendar_source(market_client, market_record):
    with Session(market_client.app.state.engine) as db, db.begin():
        product = db.get(Product, market_record["product"]["id"])
        product.created_at = datetime(2024, 1, 1)
    return market_record


@pytest.fixture
def seed_calendar(market_client, calendar_source, payload):
    """Historical dates/amounts are synthetic records in the temporary test database only."""

    def seed(
        day,
        cost="2",
        *,
        unit="loaf",
        kind="sourdough",
        version="production-economics-v1",
        currency="USD",
        count=1,
        product_id=None,
    ):
        inputs = deepcopy(payload)
        inputs.update(
            sellable_units=1,
            labor=[],
            proposed_prices=[],
            costs=[
                {"label": "PRIVATE_CALENDAR_COST_LABEL", "category": "materials", "amount": cost}
            ],
        )
        result = calculate(PricingRequest.model_validate(inputs)).model_dump(mode="json")
        result["currency"] = currency
        identifier = product_id or calendar_source["product"]["id"]
        snapshot = {
            **calendar_source["product"],
            "id": identifier,
            "product_type": kind,
            "selling_unit": unit,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        ids = []
        with Session(market_client.app.state.engine) as db, db.begin():
            for _ in range(count):
                row_id = str(uuid4())
                db.add(
                    Analysis(
                        id=row_id,
                        product_id=identifier,
                        created_at=datetime.combine(day, time(12)),
                        calculation_version=version,
                        product_snapshot=snapshot,
                        inputs=inputs,
                        result=result,
                    )
                )
                ids.append(row_id)
        return ids[0] if count == 1 else ids

    return seed
