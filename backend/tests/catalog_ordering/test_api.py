from copy import deepcopy

import pytest
from sqlalchemy.orm import Session

from fairmade.models import MarketplaceListing

PATH = "/api/v1/marketplace/listings"


def ids(response):
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_listed_price_ordering_and_default_shape(market_client, ordered_listing):
    high, low = ordered_listing("17.00"), ordered_listing("7.00")
    default = market_client.get(PATH)
    assert "ordering" not in default.json()
    assert ids(market_client.get(PATH + "?sort=price_asc")) == [
        low["listing"]["id"],
        high["listing"]["id"],
    ]
    assert ids(market_client.get(PATH + "?sort=price_desc")) == [
        high["listing"]["id"],
        low["listing"]["id"],
    ]
    assert market_client.get(PATH + "?sort=price_asc").headers["cache-control"] == "no-store"


def test_quality_uses_only_explicit_public_disclosures(market_client, ordered_listing):
    match = ordered_listing("30.00", quality=True)
    unknown = ordered_listing("8.00")
    flagged = ordered_listing("1.00", quality=False)
    hidden = ordered_listing("0.50", quality=False, disclose=False)
    response = market_client.get(PATH + "?sort=quality")
    actual = ids(response)
    assert actual[0] == match["listing"]["id"] and actual[-1] == flagged["listing"]["id"]
    signals = {item["listing_id"]: item for item in response.json()["ordering"]["items"]}
    assert signals[match["listing"]["id"]]["quality_status"] == "claims_match_unverified"
    assert signals[hidden["listing"]["id"]]["quality_status"] == "undisclosed"
    assert signals[unknown["listing"]["id"]]["quality_status"] == "undisclosed"
    assert "PRIVATE_" not in response.text
    assert "seller_reported_unverified" in response.text


def test_unit_prices_compare_contents_not_listed_package_prices(market_client, ordered_listing):
    small = ordered_listing("8.00", contents={"value": "250", "unit": "g"})
    large = ordered_listing("12.00", contents={"value": "1000", "unit": "g"})
    response = market_client.get(PATH + "?sort=unit_price&product_type=sourdough&reference_unit=kg")
    assert ids(response) == [large["listing"]["id"], small["listing"]["id"]]
    assert response.json()["ordering"]["compared_count"] == 2
    assert response.json()["items"][0]["payload"]["price"]["amount"] == "12.00"


def test_value_quality_availability_price_hierarchy(market_client, ordered_listing):
    matched = ordered_listing("30.00", quality=True)
    unknown_stock = ordered_listing("1.00", quality=True, stock=None)
    unknown_quality = ordered_listing("0.50")
    failed = ordered_listing("0.10", quality=False)
    unavailable = ordered_listing("0.20", quality=True, stock=0)
    response = market_client.get(PATH + "?sort=value&product_type=sourdough&reference_unit=kg")
    actual = ids(response)
    assert actual[:3] == [
        matched["listing"]["id"],
        unknown_stock["listing"]["id"],
        unknown_quality["listing"]["id"],
    ]
    signals = {item["listing_id"]: item for item in response.json()["ordering"]["items"]}
    assert signals[failed["listing"]["id"]]["comparison_status"] == "not_compared"
    assert "QUALITY_REQUIRES_ATTENTION" in signals[failed["listing"]["id"]]["reasons"]
    assert signals[unavailable["listing"]["id"]]["comparison_status"] == "not_compared"
    assert response.json()["ordering"]["compared_count"] == 3


def test_incompatible_and_legacy_units_are_not_compared(market_client, ordered_listing):
    comparable = ordered_listing()
    wrong = ordered_listing(contents={"value": "1", "unit": "loaf"})
    legacy = ordered_listing()
    with Session(market_client.app.state.engine) as db, db.begin():
        listing = db.get(MarketplaceListing, legacy["listing"]["id"])
        payload = deepcopy(listing.public_payload)
        payload.pop("unit_price", None)
        payload.pop("selling_quantity", None)
        listing.public_payload = payload
    response = market_client.get(PATH + "?sort=unit_price&product_type=sourdough&reference_unit=kg")
    assert ids(response)[0] == comparable["listing"]["id"]
    signals = {item["listing_id"]: item for item in response.json()["ordering"]["items"]}
    assert signals[wrong["listing"]["id"]]["reasons"] == ["INCOMPATIBLE_REFERENCE_UNIT"]
    assert signals[legacy["listing"]["id"]]["reasons"] == ["UNIT_PRICE_MISSING"]


def test_full_scope_ordered_before_pagination_and_ties_are_stable(market_client, ordered_listing):
    low, high, medium = ordered_listing("1.00"), ordered_listing("10.00"), ordered_listing("5.00")
    full = market_client.get(PATH + "?sort=price_asc")
    assert ids(full) == [low["listing"]["id"], medium["listing"]["id"], high["listing"]["id"]]
    pages = [
        market_client.get(PATH + f"?sort=price_asc&limit=1&offset={offset}") for offset in range(3)
    ]
    assert [ids(response)[0] for response in pages] == ids(full)
    assert ids(market_client.get(PATH + "?sort=price_asc&offset=50")) == []


def test_filters_apply_before_complete_scope_cap(market_client, ordered_listing, monkeypatch):
    import fairmade.catalog_ordering.repository as repository

    ordered_listing("1.00", location="Elsewhere")
    expected = ordered_listing("10.00", location="Exampletown")
    monkeypatch.setattr(repository, "MAX_CANDIDATES", 1)
    broad = market_client.get(PATH + "?sort=quality")
    assert broad.status_code == 409
    assert broad.json()["detail"]["code"] == "ORDERING_SCOPE_TOO_LARGE"
    assert broad.headers["cache-control"] == "no-store"
    assert ids(market_client.get(PATH + "?sort=quality&location=exampletown")) == [
        expected["listing"]["id"]
    ]


@pytest.mark.parametrize(
    "query",
    [
        "sort=unknown",
        "sort=value",
        "sort=unit_price&product_type=sourdough",
        "reference_unit=kg",
        "sort=price_asc&reference_unit=kg",
        "sort=value&product_type=sourdough&reference_unit=invalid",
    ],
)
def test_invalid_ordering_scope(market_client, query):
    response = market_client.get(PATH + "?" + query)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
