from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, localcontext

import pytest
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import SellerPricingReview
from fairmade.price_advice.domain import cent_range


def read(client, headers, source):
    return client.post(
        source["advice_path"], headers=headers, json={"review_id": source["advice_review"]["id"]}
    )


def test_conditional_overlap_and_immutable_review_with_source_privacy(
    market_client, market_headers, advice_source
):
    source = advice_source()
    response = read(market_client, market_headers, source)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["status"] == "conditional_overlap"
    assert report["quality_status"] == "selected_claims_match_unverified"
    assert (
        report["recommended_review_range"]
        == source["analysis"]["result"]["sustainable_price_range"]
    )
    assert len(report["market_sources"]) == 2
    assert report["production_unit_quantity"] == {"value": "1", "unit": "loaf"}
    assert report["market_reference_quantity"] == {"value": "1", "unit": "loaf"}
    assert "PRIVATE_COMPARATOR" not in response.text
    assert response.headers["cache-control"] == "no-store"
    with Session(market_client.app.state.engine) as db:
        saved = db.get(SellerPricingReview, source["advice_review"]["id"])
        assert saved.result == source["advice_review"]["result"]


@pytest.mark.parametrize("quality", ["failed", "unknown", "missing", "outdated"])
def test_quality_failures_unknowns_missing_and_stale_checks_block_recommendation(
    market_client, market_headers, advice_source, quality
):
    source = advice_source(quality=quality)
    response = read(market_client, market_headers, source)
    assert response.status_code == 200
    assert response.json()["status"] == "quality_blocked"
    assert response.json()["recommended_review_range"] is None


@pytest.mark.parametrize("market,mapping", [(False, True), (True, False)])
def test_missing_market_or_mapping_is_explicitly_economics_only(
    market_client, market_headers, advice_source, market, mapping
):
    source = advice_source(market=market, mapping=mapping, quality="not_configured")
    response = read(market_client, market_headers, source)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "economics_only" and body["quality_status"] == "not_configured"
    assert body["recommended_review_range"] == body["seller_target_range"]
    assert body["selected_market_range"] is None
    assert body["production_unit_quantity"] is None
    assert body["market_reference_quantity"] == ({"value": "1", "unit": "loaf"} if market else None)


@pytest.mark.parametrize(
    "prices,status", [(["0.01"], "target_market_gap"), (["999999999.00"], "market_premium_gap")]
)
def test_nonoverlap_does_not_cut_targets_or_choose_highest_market_price(
    market_client, market_headers, advice_source, prices, status
):
    source = advice_source(prices)
    response = read(market_client, market_headers, source)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == status and body["recommended_review_range"] is None
    if status == "target_market_gap":
        assert "MARKET_REFERENCE_BELOW_MODELED_BREAK_EVEN" in body["reasons"]


def test_current_selling_unit_change_blocks_old_analysis_basis(
    market_client, market_headers, advice_source
):
    source = advice_source()
    assert (
        market_client.patch(
            source["path"], headers=market_headers, json={"selling_unit": "pair"}
        ).status_code
        == 200
    )
    response = read(market_client, market_headers, source)
    assert response.status_code == 200
    assert response.json()["status"] == "basis_changed"
    assert response.json()["recommended_review_range"] is None
    assert response.json()["analysis_selling_unit"] == "loaf"
    assert response.json()["current_selling_unit"] == "pair"


def test_comparison_freshness_is_reassessed_without_changing_saved_review(
    market_client, market_headers, advice_source, monkeypatch
):
    source = advice_source()
    monkeypatch.setattr(
        "fairmade.price_advice.service.today", lambda: utcnow().date() + timedelta(days=31)
    )
    response = read(market_client, market_headers, source)
    assert response.status_code == 200
    assert response.json()["status"] == "economics_only"
    assert response.json()["market_status"] == "no_comparable_evidence"
    assert all(not row["included"] for row in response.json()["market_sources"])


def test_cent_rounding_stays_inside_both_bounds_and_publication_limits():
    with localcontext() as context:
        context.prec = 2
        result = cent_range(Decimal("8.001"), Decimal("9.999"))
        assert result.minimum == Decimal("8.01") and result.maximum == Decimal("9.99")
        assert cent_range(Decimal("8.001"), Decimal("8.009")) is None
        assert cent_range(Decimal(0), Decimal(0)) is None
        assert cent_range(Decimal("1000000000.001"), Decimal("1000000001")) is None


def test_overlap_without_a_supported_cent_returns_no_recommendation(
    market_client, market_headers, advice_source
):
    def observed_prices(bounds):
        minimum = Decimal(bounds["minimum"])
        return [str(minimum + Decimal("0.001")), str(minimum + Decimal("0.009"))]

    source = advice_source(observed_prices)
    response = read(market_client, market_headers, source)
    assert response.status_code == 200
    assert response.json()["status"] == "no_cent_price"
    assert response.json()["recommended_review_range"] is None


@pytest.mark.parametrize("amount", [None, "1000000000"])
def test_zero_or_out_of_publication_bounds_models_do_not_get_an_actionable_range(
    market_client, market_headers, advice_source, payload, amount
):
    source = advice_source(market=False, quality="not_configured")
    inputs = deepcopy(payload)
    inputs.update(
        costs=[],
        labor=[],
        sellable_units=1,
        proposed_prices=[],
        payment_fees={"rate": "0", "fixed_per_order": "0", "units_per_order": 1},
    )
    if amount is not None:
        inputs["costs"] = [
            {"label": "Synthetic large material input", "category": "materials", "amount": amount}
        ]
    analysis = market_client.post(source["path"] + "/analyses", headers=market_headers, json=inputs)
    assert analysis.status_code == 201
    review = market_client.post(
        source["path"] + "/pricing-reviews",
        headers=market_headers,
        json={"pricing_analysis_id": analysis.json()["id"]},
    )
    assert review.status_code == 201
    source["advice_review"] = review.json()
    response = read(market_client, market_headers, source)
    assert response.status_code == 200
    assert response.json()["status"] == "no_cent_price"
    assert response.json()["recommended_review_range"] is None
    assert "NO_LABOR_COST" in response.json()["notices"]


def test_auth_role_ownership_invalid_source_and_private_errors(
    market_client, market_headers, buyer_headers, market_account, market_source, advice_source
):
    source = advice_source()
    request = {"review_id": source["advice_review"]["id"]}
    assert market_client.post(source["advice_path"], json=request).status_code == 401
    assert read(market_client, buyer_headers, source).status_code == 403
    other = market_account("other-price-advice-seller@example.com")
    assert read(market_client, other, source).status_code == 404
    foreign = market_source()
    assert (
        market_client.post(
            foreign["path"] + "/pricing-recommendations", headers=market_headers, json=request
        ).status_code
        == 404
    )
    error = market_client.post(
        source["advice_path"],
        headers=market_headers,
        json={**request, "secret": "PRIVATE_FAKE_VALUE"},
    )
    assert error.status_code == 422 and "PRIVATE_FAKE_VALUE" not in error.text
    assert error.headers["cache-control"] == "no-store"
