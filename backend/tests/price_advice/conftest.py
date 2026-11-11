import json

import pytest

from fairmade.database import utcnow
from fairmade.price_advice.integration import TITLE


class AdviceGateway:
    def __init__(self):
        self.calls = []
        self.prices = []
        self.after = None

    def complete(self, messages, schema):
        self.calls.append(messages)
        if "proposed_prices" in schema["properties"]:
            return {"proposed_prices": self.prices}
        if self.after:
            self.after()
        facts = json.loads(messages[-1]["content"])["EVIDENCE"]
        key = next(fact["key"] for fact in facts if fact["title"] == TITLE)
        return {
            "paragraphs": [
                {
                    "text": "Review conditional evidence and preserve mandatory requirements.",
                    "evidence_keys": [key],
                }
            ]
        }


@pytest.fixture
def advice_gateway(market_client):
    gateway = AdviceGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def advice_source(market_client, market_headers, market_source):
    def create(prices=None, *, quality="passed", market=True, mapping=True):
        source = market_source()
        path = source["path"]
        evaluations = []
        if quality != "not_configured":
            rule = {
                "key": "flag",
                "label": "Synthetic mandatory requirement",
                "type": "boolean",
                "expected": True,
            }
            response = market_client.put(
                path + "/quality-locks",
                headers=market_headers,
                json={
                    "expected_revision": 0,
                    "rules": [rule],
                },
            )
            assert response.status_code == 200
            if quality != "missing":
                response = market_client.post(
                    path + "/quality-evaluations",
                    headers=market_headers,
                    json={
                        "candidate_label": "Synthetic selected production claim",
                        "expected_revision": 1,
                        "claims": {}
                        if quality == "unknown"
                        else {"flag": {"type": "boolean", "value": quality != "failed"}},
                    },
                )
                assert response.status_code == 201, response.text
                evaluations.append(response.json()["id"])
                if quality == "outdated":
                    assert (
                        market_client.put(
                            path + "/quality-locks",
                            headers=market_headers,
                            json={"expected_revision": 1, "rules": [rule]},
                        ).status_code
                        == 200
                    )
        comparison = None
        if market:
            bounds = source["analysis"]["result"]["sustainable_price_range"]
            values = prices(bounds) if callable(prices) else prices
            if values is None:
                values = [bounds["minimum"], bounds["maximum"]]
            ids = []
            for index, price in enumerate(values):
                response = market_client.post(
                    path + "/price-observations",
                    headers=market_headers,
                    json={
                        "label": f"Synthetic comparator {index}",
                        "product_type": "sourdough",
                        "currency": "USD",
                        "price": price,
                        "quantity": {"value": "1", "unit": "loaf"},
                        "source": {
                            "name": "Fictional observation",
                            "kind": "document",
                            "reference": "Synthetic fixture, not a real local price",
                        },
                        "location": "Exampletown",
                        "observed_on": utcnow().date().isoformat(),
                        "quality_notes": "PRIVATE_COMPARATOR_QUALITY_NOTES",
                        "price_notes": "PRIVATE_COMPARATOR_PRICE_NOTES",
                    },
                )
                assert response.status_code == 201, response.text
                ids.append(response.json()["id"])
            response = market_client.post(
                path + "/price-comparisons",
                headers=market_headers,
                json={"observation_ids": ids, "target_quantity": {"value": "1", "unit": "loaf"}},
            )
            assert response.status_code == 201, response.text
            comparison = response.json()
        request = {
            "pricing_analysis_id": source["analysis"]["id"],
            "quality_evaluation_ids": evaluations,
        }
        if comparison:
            request["comparison_report_id"] = comparison["id"]
            if mapping:
                request["production_unit_quantity"] = {"value": "1", "unit": "loaf"}
        response = market_client.post(
            path + "/pricing-reviews", headers=market_headers, json=request
        )
        assert response.status_code == 201, response.text
        return {
            **source,
            "advice_review": response.json(),
            "comparison": comparison,
            "advice_path": path + "/pricing-recommendations",
        }

    return create
