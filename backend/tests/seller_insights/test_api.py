from copy import deepcopy
from datetime import datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import Analysis, Product
from fairmade.pricing.schemas import PricingRequest
from fairmade.pricing.service import calculate


def test_full_scope_limit_refuses_report_instead_of_silently_dropping_cost_history(
    market_client, market_headers, insight_listing
):
    source = insight_listing()
    with Session(market_client.app.state.engine) as db, db.begin():
        original = db.get(Analysis, source["analysis"]["id"])
        for _ in range(26):
            db.add(
                Analysis(
                    product_id=original.product_id,
                    created_at=utcnow() - timedelta(days=2),
                    calculation_version=original.calculation_version,
                    product_snapshot=original.product_snapshot,
                    inputs=original.inputs,
                    result=original.result,
                )
            )
    response = market_client.post(source["path"] + "/insights", headers=market_headers, json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "INSIGHT_SCOPE_TOO_LARGE"
    assert "alerts" not in response.json()


def test_closed_utc_windows_exclude_other_owners_and_today(
    market_client, market_headers, market_account, insight_listing, receipt_evidence
):
    source = insight_listing()
    other = market_account("other-insight-receipts@example.com")
    owner = market_client.get("/api/v1/auth/me", headers=other).json()["id"]
    receipt_evidence("999.00", account_id=owner)
    receipt_evidence("777.00", days_ago=0)
    receipt_evidence("10.00", days_ago=30)
    receipt_evidence("20.00", days_ago=60)
    receipt_evidence("888.00", days_ago=61)
    response = market_client.post(source["path"] + "/insights", headers=market_headers, json={})
    assert response.status_code == 200
    body = response.json()
    assert body["receipts"]["current"]["recorded_total"] == "10.00"
    assert body["receipts"]["previous"]["recorded_total"] == "20.00"
    assert body["receipts"]["difference"]["change"] == "-10.000000"


def test_current_price_alert_and_missing_record_coverage(
    market_client,
    market_headers,
    insight_listing,
):
    source = insight_listing()
    before = market_client.get(source["path"] + "/listing", headers=market_headers).json()
    response = market_client.post(source["path"] + "/insights", headers=market_headers, json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pricing"]["status"] == "assessed"
    assert body["pricing"]["below_break_even"] is True
    assert "UNSUSTAINABLE_PRICE" in [alert["code"] for alert in body["alerts"]]
    assert body["receipts"]["difference"]["change"] is None
    assert body["production"]["sellable_fraction"] is None
    assert body["materials"] == []
    assert response.headers["cache-control"] == "no-store"
    assert market_client.get(source["path"] + "/listing", headers=market_headers).json() == before


def test_low_margin_uses_existing_seller_targets(
    market_client, market_headers, insight_listing, payload
):
    result = calculate(PricingRequest.model_validate(payload))
    source = insight_listing(str(result.break_even_price))
    body = market_client.post(source["path"] + "/insights", headers=market_headers, json={}).json()
    assert body["pricing"]["below_break_even"] is False
    assert body["pricing"]["below_target_margin"] is True
    assert "LOW_MARGIN" in [alert["code"] for alert in body["alerts"]]


def test_receipt_increase_is_seller_wide_and_not_subtracted_from_profit(
    market_client,
    market_headers,
    insight_listing,
    receipt_evidence,
):
    source = insight_listing()
    original = market_client.post(
        source["path"] + "/insights", headers=market_headers, json={}
    ).json()
    receipt_evidence("10.00", days_ago=40)
    receipt_evidence("30.00", days_ago=2)
    receipt_evidence("999.00", days_ago=2, approved=False)
    body = market_client.post(source["path"] + "/insights", headers=market_headers, json={}).json()
    assert body["receipts"]["difference"]["change"] == "20.000000"
    assert body["receipts"]["difference"]["relative_change"] == "2.000000"
    assert body["receipts"]["current"]["receipt_count"] == 1
    assert body["pricing"]["profit_per_unit"] == original["pricing"]["profit_per_unit"]
    assert any(
        alert["scope"] == "seller" and alert["code"] == "REVIEWED_EXPENSE_TOTAL_INCREASE"
        for alert in body["alerts"]
    )
    assert "PRIVATE_RECEIPT" not in str(body)


def test_one_receipt_period_missing_is_not_a_zero_spend_baseline(
    market_client,
    market_headers,
    insight_listing,
    receipt_evidence,
):
    source = insight_listing()
    receipt_evidence("30.00")
    body = market_client.post(source["path"] + "/insights", headers=market_headers, json={}).json()
    assert body["receipts"]["difference"]["change"] is None
    assert "REVIEWED_EXPENSE_TOTAL_INCREASE" not in [alert["code"] for alert in body["alerts"]]


def test_saved_cost_increase_between_compatible_periods(
    market_client,
    market_headers,
    insight_listing,
    payload,
):
    source = insight_listing()
    for age, amount in [(40, "10"), (2, "100")]:
        inputs = deepcopy(payload)
        inputs["costs"][0]["amount"] = amount
        saved = market_client.post(
            source["path"] + "/analyses", headers=market_headers, json=inputs
        )
        assert saved.status_code == 201
        with Session(market_client.app.state.engine) as db, db.begin():
            db.get(Analysis, saved.json()["id"]).created_at = datetime.combine(
                utcnow().date() - timedelta(days=age), time(12)
            )
    body = market_client.post(source["path"] + "/insights", headers=market_headers, json={}).json()
    assert body["costs"]["status"] == "available"
    assert Decimal(body["costs"]["difference"]["change"]) > 0
    assert "SAVED_UNIT_COST_INCREASE" in [alert["code"] for alert in body["alerts"]]


def test_effective_production_corrections_and_basis_changes(
    market_client,
    market_headers,
    insight_listing,
    production_evidence,
):
    source = insight_listing()
    first = production_evidence(source)
    before = market_client.post(
        source["path"] + "/insights", headers=market_headers, json={}
    ).json()
    assert before["production"]["non_sellable_units"] == 3
    assert "NON_SELLABLE_OUTPUT" in [alert["code"] for alert in before["alerts"]]
    production_evidence(source, sellable=10, correction=first["id"])
    after = market_client.post(source["path"] + "/insights", headers=market_headers, json={}).json()
    assert after["production"]["included_records"] == 1
    assert after["production"]["non_sellable_units"] == 0
    with Session(market_client.app.state.engine) as db, db.begin():
        db.get(Product, source["product"]["id"]).selling_unit = "item"
    changed = market_client.post(
        source["path"] + "/insights", headers=market_headers, json={}
    ).json()
    assert changed["pricing"]["status"] == "incompatible_basis"
    assert changed["production"]["included_records"] == 0
    assert changed["production"]["excluded_basis_records"] == 1


def test_material_waste_is_per_material_unit_and_no_value_is_invented(
    market_client,
    market_headers,
    insight_listing,
):
    source = insight_listing()
    material = market_client.post(
        "/api/v1/seller/materials",
        headers=market_headers,
        json={"name": "PRIVATE_FLOUR_MATERIAL", "unit": "g"},
    ).json()
    path = "/api/v1/seller/materials/" + material["id"] + "/movements"
    for revision, kind, quantity in [(1, "receipt", "1000"), (2, "waste", "50")]:
        moved = market_client.post(
            path,
            headers=market_headers,
            json={
                "request_id": str(uuid4()),
                "expected_revision": revision,
                "kind": kind,
                "quantity": quantity,
                "unit": "g",
                "occurred_on": (utcnow().date() - timedelta(days=2)).isoformat(),
                "reason": "PRIVATE_WASTE_REASON",
            },
        )
        assert moved.status_code == 201, moved.text
    body = market_client.post(source["path"] + "/insights", headers=market_headers, json={}).json()
    assert Decimal(body["materials"][0]["quantity"]) == 50
    assert body["materials"][0]["unit"] == "g"
    assert "RECORDED_MATERIAL_WASTE" in [alert["code"] for alert in body["alerts"]]
    assert "PRIVATE_WASTE_REASON" not in str(body)


def test_access_missing_evidence_and_foreign_analysis(
    market_client,
    market_headers,
    buyer_headers,
    market_account,
    market_source,
    insight_listing,
):
    source = insight_listing()
    path = source["path"] + "/insights"
    assert market_client.post(path, json={}).status_code == 401
    assert market_client.post(path, headers=buyer_headers, json={}).status_code == 403
    outsider = market_account("other-insight@example.com")
    assert market_client.post(path, headers=outsider, json={}).status_code == 404
    foreign = market_source(headers=outsider)
    assert (
        market_client.post(
            path, headers=market_headers, json={"analysis_id": foreign["analysis"]["id"]}
        ).status_code
        == 404
    )
    product = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={"name": "New product", "product_type": "other", "selling_unit": "item"},
    ).json()
    response = market_client.post(
        "/api/v1/products/" + product["id"] + "/insights", headers=market_headers, json={}
    )
    assert (
        response.status_code == 200 and response.json()["pricing"]["status"] == "missing_analysis"
    )


@pytest.mark.parametrize(
    "body",
    [
        {"period_days": True},
        {"period_days": "30"},
        {"period_days": 0},
        {"period_days": 91},
        {"spend": "PRIVATE_FAKE_VALUE"},
        {"analysis_id": "not-a-uuid"},
    ],
)
def test_bounded_private_input(market_client, market_headers, insight_listing, body):
    source = insight_listing()
    response = market_client.post(source["path"] + "/insights", headers=market_headers, json=body)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert "PRIVATE_FAKE_VALUE" not in response.text
