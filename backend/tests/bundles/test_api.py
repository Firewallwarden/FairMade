from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from baskets.conftest import save_profile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import Order, PayPalCheckout

BUYER = "/api/v1/buyer/bundles/suggest"
SELLER = "/api/v1/seller/bundles/suggest"


def test_exact_pair_prices_and_cart_handoff_without_writes(
    market_client, buyer_headers, bundle_body
):
    response = market_client.post(BUYER, headers=buyer_headers, json=bundle_body)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligible_pairs"] == 3
    assert [row["subtotal"]["amount"] for row in body["suggestions"]] == ["0.30", "5.11", "5.21"]
    assert all(row["quantity_each"] == 1 for row in body["suggestions"])
    assert all(row["observed_copurchase_orders"] is None for row in body["suggestions"])
    assert response.headers["cache-control"] == "no-store"
    preview = market_client.post(
        "/api/v1/orders/preview", headers=buyer_headers, json=body["suggestions"][0]["cart"]
    )
    assert preview.status_code == 200
    assert preview.json()["subtotal"]["amount"] == "0.30"
    assert "PRIVATE_MARKET" not in response.text
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 0
        assert db.scalar(select(func.count()).select_from(PayPalCheckout)) == 0


def test_budget_boundary_and_no_invented_discount(market_client, buyer_headers, bundle_body):
    for budget, expected in [("0.30", 1), ("0.29", 0), ("0.00", 0)]:
        response = market_client.post(
            BUYER, headers=buyer_headers, json={**bundle_body, "budget": budget}
        )
        assert response.status_code == 200
        assert response.json()["eligible_pairs"] == expected
        assert response.json()["budget_excluded_pairs"] == 3 - expected


def test_per_item_profile_constraints_cannot_be_overridden_by_pair_budget(
    market_client, buyer_headers, bundle_body
):
    save_profile(market_client, buyer_headers, {"budget_per_item": "0.15"})
    response = market_client.post(BUYER, headers=buyer_headers, json=bundle_body)
    assert response.status_code == 200
    assert response.json()["personalized"] is True
    assert response.json()["suggestions"] == []
    assert sum(not row["eligible"] for row in response.json()["candidates"]) == 2


def test_no_activity_without_consent(market_client, buyer_headers, bundle_body, monkeypatch):
    import fairmade.bundles.service as service

    def forbidden(*args):
        raise AssertionError("Activity must not be queried without consent")

    monkeypatch.setattr(service, "signals", forbidden)
    assert market_client.post(BUYER, headers=buyer_headers, json=bundle_body).status_code == 200


def test_missing_or_insufficient_stock_excludes_without_using_unknown_as_available(
    market_client, buyer_headers, bundle_store, bundle_listing
):
    sources = [bundle_listing(stock=0), bundle_listing(stock=None), bundle_listing(stock=2)]
    response = market_client.post(
        BUYER,
        headers=buyer_headers,
        json={
            "storefront_id": bundle_store,
            "candidates": [
                {"listing_id": row["listing"]["id"], "expected_listing_revision": 1}
                for row in sources
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"] == []
    assert "INSUFFICIENT_STOCK" in body["candidates"][0]["exclusions"]
    assert "INVENTORY_NOT_CONFIGURED" in body["candidates"][1]["exclusions"]


def test_access_foreign_store_self_purchase_and_stale_revision(
    market_client, buyer_headers, market_headers, market_account, bundle_body
):
    assert market_client.post(BUYER, json=bundle_body).status_code == 401
    assert market_client.post(SELLER, headers=buyer_headers, json=bundle_body).status_code == 403
    other = market_account("bundle-other-seller@example.com")
    assert market_client.post(SELLER, headers=other, json=bundle_body).status_code == 404
    assert market_client.post(BUYER, headers=market_headers, json=bundle_body).status_code == 409
    stale = deepcopy(bundle_body)
    stale["candidates"][0]["expected_listing_revision"] = 99
    response = market_client.post(BUYER, headers=buyer_headers, json=stale)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "LISTING_CHANGED"


def test_seller_patterns_are_private_and_refund_requests_exclude_orders(
    paypal_client, fake_gateway, market_headers, buyer_headers, bundle_body, bundle_sources
):
    expensive = [bundle_sources[0], bundle_sources[2]]
    cart = {
        "items": [
            {
                "listing_id": row["listing"]["id"],
                "expected_listing_revision": 1,
                "quantity": 1,
            }
            for row in expensive
        ]
    }
    order = paypal_client.post(
        "/api/v1/orders", headers={**buyer_headers, "Idempotency-Key": str(uuid4())}, json=cart
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]
    path = "/api/v1/orders/" + order_id + "/paypal-checkout"
    checkout = paypal_client.post(path, headers=buyer_headers, json={})
    assert checkout.status_code == 200, checkout.text
    fake_gateway.approve(checkout.json()["provider_order_id"])
    capture = paypal_client.post(path + "/capture", headers=buyer_headers, json={})
    assert capture.status_code == 200, capture.text
    with Session(paypal_client.app.state.engine) as db, db.begin():
        row = db.scalar(select(PayPalCheckout).where(PayPalCheckout.order_id == order_id))
        row.verified_at = utcnow() - timedelta(days=2)
    response = paypal_client.post(SELLER, headers=market_headers, json=bundle_body)
    assert response.status_code == 200, response.text
    first = response.json()["suggestions"][0]
    assert first["subtotal"]["amount"] == "5.11"  # observed pair beats cheaper unobserved pair
    assert first["observed_copurchase_orders"] == 1 and first["cart"] is None
    assert "PRIVATE_PAYER" not in response.text and order_id not in response.text
    public = paypal_client.post(BUYER, headers=buyer_headers, json=bundle_body).json()
    assert all(pair["observed_copurchase_orders"] is None for pair in public["suggestions"])
    refund = paypal_client.post(
        "/api/v1/orders/" + order_id + "/refund-request",
        headers=buyer_headers,
        json={"reason": "Synthetic refund request"},
    )
    assert refund.status_code == 201, refund.text
    after = paypal_client.post(SELLER, headers=market_headers, json=bundle_body).json()
    assert all(pair["observed_copurchase_orders"] == 0 for pair in after["suggestions"])


@pytest.mark.parametrize(
    "change",
    [
        {"limit": True},
        {"limit": 5},
        {"limit": 0},
        {"candidates": []},
        {"budget": "0.001"},
        {"budget": "1" * 65},
        {"private": "SECRET_SYNTHETIC"},
    ],
)
def test_bounded_redacted_input(market_client, buyer_headers, bundle_body, change):
    response = market_client.post(BUYER, headers=buyer_headers, json={**bundle_body, **change})
    assert response.status_code == 422
    assert "SECRET_SYNTHETIC" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_foreign_or_repeated_candidate_and_conflicting_assistant_scope(
    market_client, buyer_headers, market_account, bundle_body, bundle_listing, bundle_gateway
):
    repeated = deepcopy(bundle_body)
    repeated["candidates"][1] = repeated["candidates"][0]
    assert market_client.post(BUYER, headers=buyer_headers, json=repeated).status_code == 422
    other = market_account("foreign-bundle-listing@example.com")
    foreign = bundle_listing(headers=other)
    request = deepcopy(bundle_body)
    request["candidates"][0]["listing_id"] = foreign["listing"]["id"]
    assert market_client.post(BUYER, headers=buyer_headers, json=request).status_code == 404
    result = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "question": "Explain.",
            "bundles": bundle_body,
            "listing_ids": [bundle_body["candidates"][0]["listing_id"]],
        },
    )
    assert result.status_code == 422


def test_large_seller_history_refuses_partial_pair_counts(
    market_client, buyer_headers, market_headers, bundle_body
):
    buyer_id = market_client.get("/api/v1/auth/me", headers=buyer_headers).json()["id"]
    seller_id = market_client.get("/api/v1/auth/me", headers=market_headers).json()["id"]
    occurred = utcnow() - timedelta(days=2)
    with Session(market_client.app.state.engine) as db, db.begin():
        for _ in range(201):
            identifier = str(uuid4())
            db.add(
                Order(
                    id=identifier,
                    buyer_account_id=buyer_id,
                    seller_account_id=seller_id,
                    idempotency_key=str(uuid4()),
                    request_hash="0" * 64,
                    status="pending_payment",
                    created_at=occurred,
                    expires_at=occurred + timedelta(minutes=15),
                    subtotal_minor=100,
                    snapshot={},
                )
            )
            db.flush()
            db.add(
                PayPalCheckout(
                    order_id=identifier,
                    merchant_id="ABCDEFGHIJKLM",
                    amount_minor=100,
                    state="completed",
                    capture_id="TEST" + uuid4().hex,
                    verified_at=occurred,
                )
            )
    response = market_client.post(SELLER, headers=market_headers, json=bundle_body)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "BUNDLE_HISTORY_TOO_LARGE"
    assert "suggestions" not in response.json()
