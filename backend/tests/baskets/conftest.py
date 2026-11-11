import json

import pytest

PATH = "/api/v1/buyer/baskets/optimize"
PROFILE = "/api/v1/buyer/personalization"


class BasketGateway:
    def __init__(self):
        self.calls = []
        self.after = None
        self.memory_output = {"budget_per_item": "40", "product_types": []}

    def complete(self, messages, schema):
        self.calls.append(messages)
        if self.after:
            self.after()
        if "budget_per_item" in schema["properties"]:
            return self.memory_output
        facts = json.loads(messages[-1]["content"])["EVIDENCE"]
        return {
            "paragraphs": [
                {
                    "text": "Review the supplied alternatives and constraints before checkout.",
                    "evidence_keys": [facts[0]["key"]],
                }
            ]
        }


@pytest.fixture
def basket_gateway(market_client):
    gateway = BasketGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def basket_listing(market_client, market_headers, market_source):
    def create(price="12.00", stock=10, contents=None, headers=None, product_type="sourdough"):
        headers = headers or market_headers
        source = market_source(price=price, headers=headers, product_type=product_type)
        path = source["path"] + "/listing"
        created = market_client.post(
            path,
            headers=headers,
            json={
                "passport_publication_id": source["publication"]["id"],
                "selling_quantity": contents or {"value": "1", "unit": "item"},
                "seller_display_name": "Example bakery",
                "location": "Exampletown",
            },
        )
        assert created.status_code == 201, created.text
        checked = market_client.get(path + "/preview", headers=headers).json()
        activated = market_client.post(
            path + "/activate",
            headers=headers,
            json={
                "expected_revision": checked["revision"],
                "preview_hash": checked["preview_hash"],
                "approved": True,
            },
        )
        assert activated.status_code == 200, activated.text
        if stock is not None:
            assert (
                market_client.put(
                    source["path"] + "/inventory",
                    headers=headers,
                    json={
                        "expected_revision": 0,
                        "selling_unit": source["product"]["selling_unit"],
                        "on_hand": stock,
                    },
                ).status_code
                == 200
            )
        return {**source, "listing": created.json()}

    return create


@pytest.fixture
def basket_store(market_client, market_headers):
    path = "/api/v1/seller/storefronts"
    created = market_client.post(
        path,
        headers=market_headers,
        json={
            "display_name": "Example bakery",
            "location": "Exampletown",
        },
    )
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    checked = market_client.get(path + "/" + identifier + "/preview", headers=market_headers).json()
    published = market_client.post(
        path + "/" + identifier + "/publish",
        headers=market_headers,
        json={
            "expected_revision": checked["revision"],
            "preview_hash": checked["preview_hash"],
            "approved": True,
        },
    )
    assert published.status_code == 200, published.text
    return identifier


def need(group_id, *sources, quantity=1):
    return {
        "group_id": group_id,
        "quantity": quantity,
        "alternatives": [
            {"listing_id": source["listing"]["id"], "expected_listing_revision": 1}
            for source in sources
        ],
    }


@pytest.fixture
def basket_body(basket_store, basket_listing):
    high, low, extra = basket_listing("17.00"), basket_listing("12.00"), basket_listing("7.00")
    return {
        "storefront_id": basket_store,
        "budget": "40.00",
        "needs": [
            need("bread", high, low, quantity=2),
            need("extra", extra),
        ],
    }


def save_profile(client, headers, preferences):
    current = client.get(PROFILE, headers=headers).json()
    response = client.put(
        PROFILE,
        headers=headers,
        json={
            "expected_revision": current["revision"],
            "enabled": True,
            "confirmed": True,
            "preferences": preferences,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()
