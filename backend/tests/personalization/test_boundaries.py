from decimal import Decimal

from fairmade.marketplace.schemas import CatalogDetail
from fairmade.passports.schemas import PublicQualitySummary
from fairmade.personalization.ranking import evaluate
from fairmade.personalization.schemas import Preferences

PATH = "/api/v1/buyer/personalization"


def test_quality_attention_is_excluded_even_for_favorite(market_client, order_source):
    identifier = order_source["listing"]["id"]
    response = market_client.get("/api/v1/marketplace/listings/" + identifier)
    assert response.status_code == 200
    listing = CatalogDetail.model_validate(response.json())
    listing.passport.payload.quality_summary = PublicQualitySummary(
        status="needs_attention",
        evaluation_count=1,
        failed_count=1,
        unknown_or_unevaluated_count=0,
        outdated_count=0,
    )
    result = evaluate(
        listing,
        Preferences(budget_per_item="100"),
        {"favorites": {identifier}, "purchases": set(), "types": {}},
    )
    assert result["eligible"] is False
    assert result["exclusions"] == ["QUALITY_REQUIRES_ATTENTION"]
    assert result["rank"][0] == 1


def test_unknown_availability_requires_explicit_request(market_client, buyer_headers, order_source):
    from sqlalchemy import delete
    from sqlalchemy.orm import Session

    from fairmade.models import SellableInventory

    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(delete(SellableInventory))
    response = market_client.post(PATH + "/suggestions", headers=buyer_headers, json={})
    assert response.status_code == 200 and response.json()["items"] == []
    unknown = market_client.post(
        PATH + "/suggestions",
        headers=buyer_headers,
        json={"include_unknown_availability": True},
    )
    assert unknown.status_code == 200
    assert unknown.json()["items"][0]["listing"]["availability"]["status"] == "unknown"


def test_favorite_ranks_first_without_overriding_explicit_type(
    market_client, market_headers, buyer_headers, order_source, market_source, enabled_profile
):
    alternative = market_source(title="Alternative eggs", price="18.00", product_type="eggs")
    path = alternative["path"]
    listing = market_client.post(
        path + "/listing",
        headers=market_headers,
        json={
            "passport_publication_id": alternative["publication"]["id"],
            "selling_quantity": {"value": "1", "unit": "item"},
            "seller_display_name": "Synthetic seller",
            "location": "Exampletown",
        },
    ).json()
    preview = market_client.get(path + "/listing/preview", headers=market_headers).json()
    assert (
        market_client.post(
            path + "/listing/activate",
            headers=market_headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        ).status_code
        == 200
    )
    assert (
        market_client.put(
            path + "/inventory",
            headers=market_headers,
            json={
                "expected_revision": 0,
                "selling_unit": "item",
                "on_hand": 10,
            },
        ).status_code
        == 200
    )
    assert (
        market_client.post(
            "/api/v1/favorites", headers=buyer_headers, json={"listing_id": listing["id"]}
        ).status_code
        == 201
    )
    response = market_client.post(PATH + "/suggestions", headers=buyer_headers, json={})
    assert response.status_code == 200
    assert response.json()["items"][0]["listing"]["id"] == listing["id"]
    assert Decimal(response.json()["items"][0]["listing"]["payload"]["price"]["amount"]) == Decimal(
        "18"
    )
    constrained = market_client.post(
        PATH + "/suggestions", headers=buyer_headers, json={"product_types": ["sourdough"]}
    )
    assert [item["listing"]["id"] for item in constrained.json()["items"]] == [
        order_source["listing"]["id"]
    ]


def test_refund_requests_remove_purchase_affinity(
    paypal_client,
    buyer_headers,
    checkout,
    checkout_path,
    unpaid_order,
    fake_gateway,
    enabled_profile,
):
    fake_gateway.approve(checkout["provider_order_id"])
    assert (
        paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={}).status_code
        == 200
    )
    refund = paypal_client.post(
        "/api/v1/orders/" + unpaid_order["id"] + "/refund-request",
        headers=buyer_headers,
        json={"reason": "Synthetic return request"},
    )
    assert refund.status_code == 201, refund.text
    response = paypal_client.post(PATH + "/suggestions", headers=buyer_headers, json={})
    assert response.status_code == 200
    assert "PREVIOUS_VERIFIED_SANDBOX_PURCHASE" not in response.text
