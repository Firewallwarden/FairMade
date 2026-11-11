import json

import pytest
from baskets import conftest as catalog_fixtures

# Reuse the established public-listing and storefront approval workflow.
bundle_listing = catalog_fixtures.basket_listing
bundle_store = catalog_fixtures.basket_store


class BundleGateway:
    def __init__(self):
        self.calls = []
        self.after = None

    def complete(self, messages, schema):
        self.calls.append(messages)
        if "proposed_prices" in schema["properties"]:
            return {"proposed_prices": []}
        if "budget_per_item" in schema["properties"]:
            return {"budget_per_item": "10", "product_types": []}
        if self.after:
            self.after()
        facts = json.loads(messages[-1]["content"])["EVIDENCE"]
        key = next(row["key"] for row in facts if "pair suggestions" in row["title"])
        return {
            "paragraphs": [
                {
                    "text": "Review the selected pair and its constraints before purchase.",
                    "evidence_keys": [key],
                }
            ]
        }


@pytest.fixture
def bundle_gateway(market_client):
    gateway = BundleGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def bundle_sources(bundle_listing):
    return [bundle_listing("0.10"), bundle_listing("0.20"), bundle_listing("5.01")]


@pytest.fixture
def bundle_body(bundle_store, bundle_sources):
    return {
        "storefront_id": bundle_store,
        "budget": "10.00",
        "candidates": [
            {
                "listing_id": row["listing"]["id"],
                "expected_listing_revision": 1,
            }
            for row in bundle_sources
        ],
    }
