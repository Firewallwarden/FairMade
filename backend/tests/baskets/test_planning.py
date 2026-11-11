from copy import deepcopy
from decimal import Decimal
from itertools import product
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fairmade.models import Order, PayPalCheckout
from fairmade.orders.schemas import CartPreview

from .conftest import PATH, need


def test_exact_minimum_and_order_preview_handoff_without_writes(
    market_client,
    buyer_headers,
    basket_body,
):
    response = market_client.post(PATH, headers=buyer_headers, json=basket_body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "ready"
    assert result["minimum_subtotal"]["amount"] == "31.00"
    assert result["remaining_budget"]["amount"] == "9.00"
    assert [item["quantity"] for item in result["cart"]["items"]] == [2, 1]
    assert (
        result["cart"]["items"][0]["listing_id"]
        == basket_body["needs"][0]["alternatives"][1]["listing_id"]
    )
    checked = market_client.post(
        "/api/v1/orders/preview", headers=buyer_headers, json=result["cart"]
    )
    assert checked.status_code == 200, checked.text
    assert CartPreview.model_validate(checked.json()) == CartPreview.model_validate(
        result["preview"]
    )
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE_MARKET" not in response.text
    assert "on_hand" not in response.text
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 0
        assert db.scalar(select(func.count()).select_from(PayPalCheckout)) == 0


def test_minimum_matches_exhaustive_combinations(
    market_client,
    buyer_headers,
    basket_store,
    basket_listing,
):
    prices = [["0.29", "0.10", "0.20"], ["3.01", "3.00"], ["2.10", "1.99"]]
    quantities = [3, 2, 5]
    body = {
        "storefront_id": basket_store,
        "needs": [
            need(str(index), *(basket_listing(price) for price in group), quantity=quantity)
            for index, (group, quantity) in enumerate(zip(prices, quantities, strict=True))
        ],
    }
    response = market_client.post(PATH, headers=buyer_headers, json=body)
    assert response.status_code == 200, response.text
    expected = min(
        sum(Decimal(p) * q for p, q in zip(combo, quantities, strict=True))
        for combo in product(*prices)
    )
    assert Decimal(response.json()["minimum_subtotal"]["amount"]) == expected


@pytest.mark.parametrize(
    "budget,status", [("31.00", "ready"), ("30.99", "over_budget"), ("0", "over_budget")]
)
def test_total_budget_never_drops_requested_quantities(
    market_client,
    buyer_headers,
    basket_body,
    budget,
    status,
):
    basket_body["budget"] = budget
    result = market_client.post(PATH, headers=buyer_headers, json=basket_body).json()
    assert result["status"] == status
    assert result["minimum_subtotal"]["amount"] == "31.00"
    if status != "ready":
        assert result["cart"] is None and result["preview"] is None
        assert all(row["chosen_listing_id"] is None for row in result["needs"])


@pytest.mark.parametrize(
    "stock,code",
    [(0, "INSUFFICIENT_STOCK"), (1, "INSUFFICIENT_STOCK"), (None, "INVENTORY_NOT_CONFIGURED")],
)
def test_insufficient_or_unknown_stock_not_a_complete_basket(
    market_client,
    buyer_headers,
    basket_store,
    basket_listing,
    stock,
    code,
):
    source = basket_listing(stock=stock)
    response = market_client.post(
        PATH,
        headers=buyer_headers,
        json={
            "storefront_id": basket_store,
            "needs": [need("required", source, quantity=2)],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "unavailable" and result["minimum_subtotal"] is None
    assert result["cart"] is None
    assert code in result["needs"][0]["candidates"][0]["exclusions"]


def test_active_order_holds_remove_cheapest_option(
    market_client,
    buyer_headers,
    basket_store,
    basket_listing,
):
    cheap, fallback = basket_listing("1.00", stock=2), basket_listing("2.00")
    held = market_client.post(
        "/api/v1/orders",
        headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
        json={
            "items": [
                {
                    "listing_id": cheap["listing"]["id"],
                    "expected_listing_revision": 1,
                    "quantity": 2,
                }
            ]
        },
    )
    assert held.status_code == 201, held.text
    response = market_client.post(
        PATH,
        headers=buyer_headers,
        json={
            "storefront_id": basket_store,
            "needs": [need("bread", cheap, fallback)],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["minimum_subtotal"]["amount"] == "2.00"


def test_smaller_contents_cannot_masquerade_as_savings(
    market_client,
    buyer_headers,
    basket_store,
    basket_listing,
):
    full = basket_listing("12.00", contents={"value": "600", "unit": "g"})
    small = basket_listing("6.00", contents={"value": "300", "unit": "g"})
    response = market_client.post(
        PATH,
        headers=buyer_headers,
        json={
            "storefront_id": basket_store,
            "needs": [need("bread", full, small)],
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "BASKET_INCOMPATIBLE_ALTERNATIVES"


def test_stale_revision_requires_review(market_client, buyer_headers, basket_body):
    basket_body["needs"][0]["alternatives"][0]["expected_listing_revision"] = 2
    response = market_client.post(PATH, headers=buyer_headers, json=basket_body)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "LISTING_CHANGED"


def test_other_seller_unpublished_and_missing_are_uniform_absence(
    market_client,
    buyer_headers,
    market_headers,
    market_account,
    basket_store,
    basket_listing,
):
    other = market_account("other-basket@example.com")
    foreign = basket_listing(headers=other)
    hidden = basket_listing()
    assert (
        market_client.post(
            hidden["path"] + "/listing/deactivate", headers=market_headers
        ).status_code
        == 204
    )
    for identifier in [foreign["listing"]["id"], hidden["listing"]["id"], str(uuid4())]:
        response = market_client.post(
            PATH,
            headers=buyer_headers,
            json={
                "storefront_id": basket_store,
                "needs": [
                    {
                        "group_id": "bread",
                        "quantity": 1,
                        "alternatives": [
                            {"listing_id": identifier, "expected_listing_revision": 1}
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_self_purchase_and_withdrawn_storefront(
    market_client,
    market_headers,
    buyer_headers,
    basket_body,
    basket_store,
):
    assert market_client.post(PATH, headers=market_headers, json=basket_body).status_code == 409
    assert (
        market_client.post(
            "/api/v1/seller/storefronts/" + basket_store + "/withdraw", headers=market_headers
        ).status_code
        == 204
    )
    assert market_client.post(PATH, headers=buyer_headers, json=basket_body).status_code == 404


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.update(budget=20),
        lambda b: b.update(budget=True),
        lambda b: b.update(budget="-1"),
        lambda b: b.update(budget="NaN"),
        lambda b: b.update(budget="1.001"),
        lambda b: b.update(budget="1000000001"),
        lambda b: b.update(needs=[]),
        lambda b: b.update(needs=b["needs"] * 3),
        lambda b: b["needs"][0].update(quantity=True),
        lambda b: b["needs"][0].update(quantity=0),
        lambda b: b["needs"][0].update(quantity=10001),
        lambda b: b["needs"][0].update(quantity=1.5),
        lambda b: b["needs"][0].update(alternatives=[]),
        lambda b: b["needs"][0].update(alternatives=b["needs"][0]["alternatives"] * 3),
        lambda b: b["needs"][0].update(group_id="PRIVATE_BAD_GROUP!"),
        lambda b: b["needs"][0]["alternatives"][0].update(price="PRIVATE_PRICE"),
        lambda b: b.update(seller_account_id="PRIVATE_ACCOUNT"),
        lambda b: b["needs"][1].update(group_id="bread"),
        lambda b: b["needs"][1].update(alternatives=b["needs"][0]["alternatives"]),
    ],
)
def test_strict_bounded_inputs_redact_private_values(
    market_client, buyer_headers, basket_body, mutate
):
    body = deepcopy(basket_body)
    mutate(body)
    response = market_client.post(PATH, headers=buyer_headers, json=body)
    assert response.status_code == 422, response.text
    assert "PRIVATE_" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_authentication_required_and_no_model_needed(market_client, basket_body):
    response = market_client.post(PATH, json=basket_body)
    assert response.status_code == 401
