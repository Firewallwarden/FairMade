import json

import pytest

from fairmade.database import utcnow


class RecommendationGateway:
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
                    "text": "Review eligible quotes while preserving mandatory requirements.",
                    "evidence_keys": [facts[-1]["key"]],
                }
            ]
        }


@pytest.fixture
def recommendation_gateway(market_client):
    gateway = RecommendationGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def supplier_scope(market_client, market_headers, market_record):
    base = market_record["path"] + "/sourcing-inputs"
    sourcing = market_client.post(base, headers=market_headers, json={"label": "Flour"})
    assert sourcing.status_code == 201
    path = base + "/" + sourcing.json()["id"]
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

    def create(specs=None, package_quantities=None):
        specs = specs or [
            ("Economical", "10.00", True, False, True),
            ("Preferred", "20.00", True, True, False),
            ("Dominated", "30.00", True, True, False),
            ("Excluded cheap", "1.00", False, True, True),
        ]
        ids = []
        for index, (name, price, organic, premium, local) in enumerate(specs):
            response = market_client.post(
                path + "/supplier-quotes",
                headers=market_headers,
                json={
                    "supplier_name": name,
                    "source": {
                        "name": "Synthetic observation",
                        "kind": "in_person",
                        "reference": "Synthetic test fixture, not a real quote",
                    },
                    "location": "Exampletown",
                    "observed_on": utcnow().date().isoformat(),
                    "currency": "USD",
                    "package_price": price,
                    "package_quantity": {
                        "value": (package_quantities or {}).get(index, "1"),
                        "unit": "kg",
                    },
                    "usable_fraction": "1",
                    "transport_cost": "0.00",
                    "availability": "available",
                    "claims": {
                        "organic": {"type": "boolean", "value": organic},
                        "premium": {"type": "boolean", "value": premium},
                        "local": {"type": "boolean", "value": local},
                    },
                    "notes": "PRIVATE_SUPPLIER_NOTES",
                },
            )
            assert response.status_code == 201, response.text
            ids.append(response.json()["id"])
        report = market_client.post(
            path + "/supplier-comparisons",
            headers=market_headers,
            json={
                "quote_ids": ids,
                "expected_rule_revision": 1,
                "required_quantity": {"value": "1", "unit": "kg"},
                "max_age_days": 30,
            },
        )
        assert report.status_code == 201, report.text
        return {
            **market_record,
            "supplier_path": path,
            "report": report.json(),
            "ids": ids,
            "recommendation_path": market_record["path"] + "/supplier-recommendations",
        }

    return create


@pytest.fixture
def supplier_body(supplier_scope):
    source = supplier_scope()
    return source, {
        "supplier_report_id": source["report"]["id"],
        "preferences": [
            {
                "key": "premium",
                "label": "Preferred grade claim",
                "type": "boolean",
                "expected": True,
            }
        ],
    }
