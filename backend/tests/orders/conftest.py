"""Shared marketplace evidence with separate buyer and initialized inventory."""

import pytest


@pytest.fixture
def buyer_headers(market_account):
    return market_account("buyer-private@example.com", roles=())


@pytest.fixture
def order_source(market_client, market_headers, market_record, listing):
    path = market_record["path"]
    preview = market_client.get(path + "/listing/preview", headers=market_headers).json()
    activated = market_client.post(
        path + "/listing/activate",
        headers=market_headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    )
    assert activated.status_code == 200
    inventory = market_client.put(
        path + "/inventory",
        headers=market_headers,
        json={"expected_revision": 0, "selling_unit": "loaf", "on_hand": 10},
    )
    assert inventory.status_code == 200, inventory.text
    return {**market_record, "listing": listing}


@pytest.fixture
def cart(order_source):
    return {
        "items": [
            {
                "listing_id": order_source["listing"]["id"],
                "expected_listing_revision": 1,
                "quantity": 2,
            }
        ]
    }
