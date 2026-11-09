import pytest


@pytest.fixture
def listing_factory(market_client, market_headers, market_source):
    def create(title="Example loaf", quantity=10):
        source = market_source(title=title)
        listing_path = source["path"] + "/listing"
        created = market_client.post(
            listing_path,
            headers=market_headers,
            json={
                "passport_publication_id": source["publication"]["id"],
                "selling_quantity": {"value": "1", "unit": "item"},
                "seller_display_name": "Example bakery",
                "location": "Exampletown",
            },
        )
        assert created.status_code == 201
        preview = market_client.get(listing_path + "/preview", headers=market_headers).json()
        assert (
            market_client.post(
                listing_path + "/activate",
                headers=market_headers,
                json={
                    "expected_revision": preview["revision"],
                    "preview_hash": preview["preview_hash"],
                    "approved": True,
                },
            ).status_code
            == 200
        )
        if quantity is not None:
            assert (
                market_client.put(
                    source["path"] + "/inventory",
                    headers=market_headers,
                    json={"expected_revision": 0, "selling_unit": "loaf", "on_hand": quantity},
                ).status_code
                == 200
            )
        return {**source, "listing": created.json()}

    return create


@pytest.fixture
def approved_storefront(market_client, market_headers):
    path = "/api/v1/seller/storefronts"
    created = market_client.post(
        path,
        headers=market_headers,
        json={
            "display_name": "Example bakery",
            "approximate_area": {"label": "Example area", "latitude": "0.00", "longitude": "0.00"},
        },
    ).json()
    preview = market_client.get(
        path + "/" + created["id"] + "/preview", headers=market_headers
    ).json()
    published = market_client.post(
        path + "/" + created["id"] + "/publish",
        headers=market_headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    )
    assert published.status_code == 200
    return created
