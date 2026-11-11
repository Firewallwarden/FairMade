import pytest

from .test_api import PATH, ids

ORIGIN = {"latitude": "0.00", "longitude": "0.00"}


def test_storefront_and_nearby_share_catalog_policy(
    market_client, ordered_storefront, ordered_listing
):
    high, low = ordered_listing("17.00"), ordered_listing("7.00")
    expected = [low["listing"]["id"], high["listing"]["id"]]
    path = "/api/v1/storefronts/" + ordered_storefront + "/listings"
    assert ids(market_client.get(path + "?sort=price_asc")) == expected
    response = market_client.post(
        "/api/v1/discovery/listings",
        json={
            "origin": ORIGIN,
            "radius_km": "10",
            "sort": "price_asc",
        },
    )
    assert response.status_code == 200, response.text
    assert [item["listing"]["id"] for item in response.json()["items"]] == expected
    assert response.json()["ordering"]["mode"] == "price_asc"
    assert all("estimated_distance_km" in item for item in response.json()["items"])
    default = market_client.post(
        "/api/v1/discovery/listings", json={"origin": ORIGIN, "radius_km": "10"}
    )
    assert default.status_code == 200 and "ordering" not in default.json()
    assert "ordering" not in market_client.get(path).json()


def test_storefront_is_scoped_and_hidden_sources_do_not_enter_ordering(
    market_client,
    market_headers,
    market_account,
    ordered_storefront,
    ordered_listing,
):
    owned = ordered_listing("12.00")
    outsider = market_account("other-ordering@example.com")
    ordered_listing("0.01", headers=outsider)
    withdrawn = ordered_listing("0.02")
    assert (
        market_client.post(
            withdrawn["path"] + "/listing/deactivate", headers=market_headers
        ).status_code
        == 204
    )
    path = "/api/v1/storefronts/" + ordered_storefront + "/listings?sort=price_asc"
    assert ids(market_client.get(path)) == [owned["listing"]["id"]]
    assert (
        market_client.post(
            "/api/v1/seller/storefronts/" + ordered_storefront + "/withdraw", headers=market_headers
        ).status_code
        == 204
    )
    assert market_client.get(path).status_code == 404


def test_availability_filters_and_publication_changes_apply_before_ordering(
    market_client,
    market_headers,
    ordered_listing,
):
    sold = ordered_listing("1.00", stock=0)
    available = ordered_listing("3.00")
    unknown = ordered_listing("2.00", stock=None)
    assert ids(market_client.get(PATH + "?sort=price_asc&availability=available")) == [
        available["listing"]["id"]
    ]
    assert ids(market_client.get(PATH + "?sort=price_asc&availability=unknown")) == [
        unknown["listing"]["id"]
    ]
    assert ids(market_client.get(PATH + "?sort=price_asc&availability=unavailable")) == [
        sold["listing"]["id"]
    ]
    withdrawn = market_client.post(
        available["draft_url"] + "/publications/" + available["publication"]["id"] + "/withdraw",
        headers=market_headers,
    )
    assert withdrawn.status_code == 204
    assert available["listing"]["id"] not in ids(market_client.get(PATH + "?sort=quality"))


@pytest.mark.parametrize(
    "body",
    [
        {"sort": "value"},
        {"sort": "unknown"},
        {"reference_unit": "kg"},
        {"sort": "unit_price", "product_type": "sourdough"},
    ],
)
def test_nearby_scope_validation(market_client, body):
    response = market_client.post(
        "/api/v1/discovery/listings",
        json={
            "origin": ORIGIN,
            "radius_km": "10",
            **body,
        },
    )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"


def test_storefront_unit_scope_and_cap(
    market_client, ordered_storefront, ordered_listing, monkeypatch
):
    import fairmade.catalog_ordering.repository as repository

    first = ordered_listing("4.00")
    ordered_listing("3.00")
    path = "/api/v1/storefronts/" + ordered_storefront + "/listings"
    assert market_client.get(path + "?sort=value").status_code == 422
    ordered = market_client.get(path + "?sort=value&product_type=sourdough&reference_unit=kg")
    assert ordered.status_code == 200
    assert first["listing"]["id"] == ids(ordered)[1]
    monkeypatch.setattr(repository, "MAX_CANDIDATES", 1)
    assert market_client.get(path + "?sort=quality").status_code == 409
