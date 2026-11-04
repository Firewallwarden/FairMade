"""Immutable cost selection, buyer privacy, ownership and capture-cohort reports."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import (
    Order,
    OrderSalesCostSnapshot,
    PayPalCheckout,
    ProductSalesCostBasis,
    RefundRequest,
)

PERIOD = "?start_date=2026-01-01&end_date=2026-02-01"
SALES = "/api/v1/seller/sales"
BACKEND = Path(__file__).parents[2]


def sales(client, headers):
    response = client.get(SALES + PERIOD, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def details(client, headers):
    response = client.get(SALES + "/orders" + PERIOD, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def selection(client, headers, source, revision, analysis_id):
    return client.put(
        source["path"] + "/sales-cost-basis",
        headers=headers,
        json={"expected_revision": revision, "analysis_id": analysis_id},
    )


def test_explicit_cost_selection_and_default_do_not_guess_a_source(
    market_client,
    market_headers,
    order_source,
):
    path = order_source["path"] + "/sales-cost-basis"
    response = market_client.get(path, headers=market_headers)
    assert response.status_code == 200
    assert response.json()["revision"] == 0
    assert response.json()["analysis_id"] is None
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(ProductSalesCostBasis)) is None
    chosen = selection(
        market_client, market_headers, order_source, 0, order_source["analysis"]["id"]
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["revision"] == 1
    assert Decimal(chosen.json()["source_snapshot"]["batch_production_cost"]) == Decimal("100")
    assert (
        selection(
            market_client,
            market_headers,
            order_source,
            0,
            None,
        ).status_code
        == 409
    )
    cleared = selection(market_client, market_headers, order_source, 1, None)
    assert cleared.status_code == 200
    assert cleared.json()["revision"] == 2
    assert cleared.json()["source_snapshot"] is None


def test_captured_order_reports_frozen_cost_profit_and_utc(
    paypal_client,
    market_headers,
    captured_sale,
    order_source,
):
    total = sales(paypal_client, market_headers)
    assert total["sales_count"] == total["covered_sales_count"] == 1
    assert total["gross_sales"] == "34.00"
    assert total["known_processing_fees"] == "1.00"
    assert total["estimated_profit"] == "13.00"
    row = details(paypal_client, market_headers)[0]
    assert row["order_id"] == captured_sale["id"]
    assert row["estimated_production_cost"] == "20.00"
    assert row["estimated_profit"] == "13.00"
    assert row["captured_at"] == "2026-01-31T12:00:00Z"
    assert (
        row["cost_snapshot"]["items"][0]["source"]["analysis_id"] == order_source["analysis"]["id"]
    )
    assert total["environment"] == "sandbox" and total["merchant_mode"] == "shared"
    assert total["period_basis"] == "capture_verified_at"


def test_cost_edits_clear_selection_and_product_edits_do_not_rewrite_order(
    paypal_client,
    market_headers,
    captured_sale,
    order_source,
    payload,
    market_url,
):
    original = details(paypal_client, market_headers)[0]
    payload["costs"][0]["amount"] = "500"
    new_analysis = paypal_client.post(
        order_source["path"] + "/analyses",
        headers=market_headers,
        json=payload,
    ).json()
    assert (
        selection(
            paypal_client,
            market_headers,
            order_source,
            1,
            new_analysis["id"],
        ).status_code
        == 200
    )
    assert selection(paypal_client, market_headers, order_source, 2, None).status_code == 200
    assert (
        paypal_client.patch(
            order_source["path"],
            headers=market_headers,
            json={"name": "Changed", "selling_unit": "bag"},
        ).status_code
        == 200
    )
    with TestClient(create_app(market_url)) as restarted:
        assert details(restarted, market_headers)[0] == original


def test_unselected_cost_never_blocks_checkout_or_fabricates_profit(
    paypal_client,
    market_headers,
    buyer_headers,
    unpaid_order,
    checkout,
    checkout_path,
    fake_gateway,
):
    fake_gateway.approve(checkout["provider_order_id"])
    assert (
        paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={}).status_code
        == 200
    )
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.get(PayPalCheckout, unpaid_order["id"]).verified_at = datetime(
            2026, 1, 31, 12, tzinfo=UTC
        )
    total = sales(paypal_client, market_headers)
    assert total["gross_sales"] == "34.00"
    assert total["estimated_profit"] is None
    assert total["missing_cost_count"] == 1
    row = details(paypal_client, market_headers)[0]
    assert row["cost_snapshot"]["items"][0]["unavailable_reason"] == "COST_BASIS_NOT_SELECTED"


def test_cost_snapshot_is_not_exposed_to_buyers_or_public_catalog(
    paypal_client,
    market_headers,
    buyer_headers,
    captured_sale,
    order_source,
    cost_selection,
):
    source_id = cost_selection["analysis_id"]
    for url in (
        "/api/v1/orders/" + captured_sale["id"],
        "/api/v1/orders",
        "/api/v1/marketplace/listings",
        "/api/v1/marketplace/listings/" + order_source["listing"]["id"],
    ):
        response = paypal_client.get(url, headers=buyer_headers)
        assert response.status_code == 200, (url, response.text)
        assert source_id not in response.text
        assert "batch_production_cost" not in response.text
        assert "cost_snapshot" not in response.text
    assert paypal_client.get(SALES + PERIOD, headers=buyer_headers).status_code == 403
    assert (
        paypal_client.get(
            order_source["path"] + "/sales-cost-basis",
            headers=buyer_headers,
        ).status_code
        == 403
    )


def test_cost_basis_and_reports_require_owner_and_verified_seller(
    paypal_client,
    market_headers,
    buyer_headers,
    captured_sale,
    order_source,
    market_account,
):
    path = order_source["path"] + "/sales-cost-basis"
    other = market_account("other-sales-seller@example.com")
    for headers, expected in (({}, 401), (buyer_headers, 403), (other, 404)):
        assert paypal_client.get(path, headers=headers).status_code == expected
        assert selection(paypal_client, headers, order_source, 1, None).status_code == expected
    for url in (SALES + PERIOD, SALES + "/orders" + PERIOD):
        assert paypal_client.get(url).status_code == 401
        assert paypal_client.get(url, headers=buyer_headers).status_code == 403
    assert sales(paypal_client, other)["sales_count"] == 0
    assert details(paypal_client, other) == []
    assert sales(paypal_client, market_headers)["sales_count"] == 1


def test_cross_product_sources_and_mismatched_units_are_rejected(
    market_client,
    market_headers,
    order_source,
    market_source,
):
    other = market_source(title="Other source")
    assert (
        selection(
            market_client,
            market_headers,
            order_source,
            0,
            other["analysis"]["id"],
        ).status_code
        == 404
    )
    assert (
        selection(market_client, market_headers, order_source, 0, str(uuid4())).status_code == 404
    )
    market_client.patch(order_source["path"], headers=market_headers, json={"selling_unit": "bag"})
    response = selection(
        market_client, market_headers, order_source, 0, order_source["analysis"]["id"]
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "COST_UNIT_MISMATCH"


def test_listing_basis_mismatch_remains_unknown_without_blocking_order(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    cost_selection,
    cart,
    payload,
):
    # The active listing still sells loaves, while the current private product uses bags.
    market_client.patch(order_source["path"], headers=market_headers, json={"selling_unit": "bag"})
    analysis = market_client.post(
        order_source["path"] + "/analyses",
        headers=market_headers,
        json=payload,
    ).json()
    assert (
        selection(market_client, market_headers, order_source, 1, analysis["id"]).status_code == 200
    )
    response = market_client.post(
        "/api/v1/orders",
        headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
        json=cart,
    )
    assert response.status_code == 201, response.text
    with Session(market_client.app.state.engine) as db:
        snapshot = db.get(OrderSalesCostSnapshot, response.json()["id"])
        assert snapshot.status == "unavailable" and snapshot.estimated_cost is None
        assert (
            snapshot.details["items"][0]["unavailable_reason"] == "COST_BASIS_UNIT_OR_TYPE_MISMATCH"
        )


def test_capture_cohort_boundaries_pagination_and_missing_fees(
    paypal_client,
    market_headers,
    captured_sale,
):
    first = details(paypal_client, market_headers)[0]
    assert sales(paypal_client, market_headers)["sales_count"] == 1
    response = paypal_client.get(
        SALES + "?start_date=2026-01-01&end_date=2026-01-31", headers=market_headers
    )
    assert response.json()["sales_count"] == 0
    response = paypal_client.get(
        SALES + "?start_date=2026-01-31&end_date=2026-02-01", headers=market_headers
    )
    assert response.json()["sales_count"] == 1
    assert (
        paypal_client.get(
            SALES + "/orders" + PERIOD + "&limit=1&offset=1", headers=market_headers
        ).json()["items"]
        == []
    )
    with Session(paypal_client.app.state.engine) as db, db.begin():
        payment = db.get(PayPalCheckout, captured_sale["id"])
        payment.fee_minor = payment.net_minor = None
    total = sales(paypal_client, market_headers)
    assert total["missing_fee_count"] == 1 and total["estimated_profit"] is None
    assert total["known_processing_fees"] == "0.00"
    assert details(paypal_client, market_headers)[0]["gross_sales"] == first["gross_sales"]


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?start_date=bad&end_date=2026-02-01",
        "?start_date=2026-02-01&end_date=2026-02-01",
        "?start_date=2026-02-01&end_date=2026-01-01",
        "?start_date=2020-01-01&end_date=2026-02-01",
    ],
)
def test_invalid_report_periods(paypal_client, market_headers, query):
    for path in (SALES, SALES + "/orders"):
        assert paypal_client.get(path + query, headers=market_headers).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"expected_revision": True, "analysis_id": None},
        {"expected_revision": 0},
        {"expected_revision": 0, "analysis_id": None, "source_snapshot": {"PRIVATE": "SECRET"}},
    ],
)
def test_strict_selection_and_redacted_validation(
    market_client, market_headers, order_source, body
):
    response = market_client.put(
        order_source["path"] + "/sales-cost-basis", headers=market_headers, json=body
    )
    assert response.status_code == 422
    assert "SECRET" not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_pending_checkout_is_not_a_sale(
    paypal_client,
    market_headers,
    checkout,
):
    assert sales(paypal_client, market_headers)["sales_count"] == 0
    assert details(paypal_client, market_headers) == []


def test_idempotent_order_retry_preserves_original_selection(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    cost_selection,
    cart,
):
    headers = {**buyer_headers, "Idempotency-Key": str(uuid4())}
    first = market_client.post("/api/v1/orders", headers=headers, json=cart)
    assert first.status_code == 201
    with Session(market_client.app.state.engine) as db:
        original = deepcopy(db.get(OrderSalesCostSnapshot, first.json()["id"]).details)
    selection(market_client, market_headers, order_source, 1, None)
    repeated = market_client.post("/api/v1/orders", headers=headers, json=cart)
    assert repeated.status_code == 200 and repeated.json() == first.json()
    with Session(market_client.app.state.engine) as db:
        assert db.get(OrderSalesCostSnapshot, first.json()["id"]).details == original
        assert len(db.scalars(select(OrderSalesCostSnapshot)).all()) == 1


def test_selection_compare_and_swap_is_atomic(market_client, market_headers, order_source):
    def choose(_):
        return selection(
            market_client, market_headers, order_source, 0, order_source["analysis"]["id"]
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(choose, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]


def test_snapshot_failure_rolls_back_order_and_reservation(
    market_client,
    buyer_headers,
    order_source,
    cost_selection,
    cart,
):
    def fail(db):
        if any(isinstance(item, OrderSalesCostSnapshot) for item in db.new):
            raise RuntimeError("Synthetic private snapshot persistence failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(market_client.app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/orders",
                headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
                json=cart,
            )
            assert response.status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    with Session(market_client.app.state.engine) as db:
        assert db.scalars(select(Order)).all() == []
        assert db.scalars(select(OrderSalesCostSnapshot)).all() == []


def test_migration_snapshot_history_guards_and_metadata(
    paypal_client,
    market_headers,
    captured_sale,
):
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    original = details(paypal_client, market_headers)
    with pytest.raises(RuntimeError, match="payment records"):
        command.downgrade(config, "0011")
    command.check(config)
    assert details(paypal_client, market_headers) == original
    with paypal_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_completed_refund_in_later_period_adjusts_original_capture_cohort(
    paypal_client,
    market_headers,
    captured_sale,
):
    with Session(paypal_client.app.state.engine) as db, db.begin():
        payment = db.get(PayPalCheckout, captured_sale["id"])
        order = db.get(Order, captured_sale["id"])
        db.add(
            RefundRequest(
                order_id=order.id,
                requested_by_account_id=order.buyer_account_id,
                reason="Synthetic completed refund",
                revision=3,
                state="refunded",
                decision="approved",
                decision_revision=1,
                decided_by_account_id=order.seller_account_id,
                decided_at=datetime(2026, 2, 1, tzinfo=UTC),
                amount_minor=payment.amount_minor,
                merchant_id=payment.merchant_id,
                capture_id=payment.capture_id,
                provider_order_id=payment.provider_order_id,
                provider_refund_id="SYNTHETICREFUND",
                provider_status="COMPLETED",
                verified_at=datetime(2026, 2, 1, tzinfo=UTC),
            )
        )
    total = sales(paypal_client, market_headers)
    assert total["completed_refunds"] == "34.00"
    assert total["estimated_profit"] == "-21.00"
    later = paypal_client.get(
        SALES + "?start_date=2026-02-01&end_date=2026-03-01",
        headers=market_headers,
    )
    assert later.json()["sales_count"] == 0


def test_upgrade_preserves_legacy_order_without_backfilling_costs(
    paypal_client,
    market_headers,
    buyer_headers,
    order_source,
    cart,
    fake_gateway,
):
    created = paypal_client.post(
        "/api/v1/orders",
        headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
        json=cart,
    )
    assert created.status_code == 201
    old_order = created.json()
    # Seed the pre-0012 state in this isolated test database: orders existed but
    # their private cost table did not. No payment or cost selection exists yet.
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.delete(db.get(OrderSalesCostSnapshot, old_order["id"]))
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0011")
    command.upgrade(config, "head")
    command.check(config)
    assert (
        paypal_client.get(
            "/api/v1/orders/" + old_order["id"],
            headers=buyer_headers,
        ).json()
        == old_order
    )
    assert (
        selection(
            paypal_client,
            market_headers,
            order_source,
            0,
            order_source["analysis"]["id"],
        ).status_code
        == 200
    )
    path = "/api/v1/orders/" + old_order["id"] + "/paypal-checkout"
    checkout = paypal_client.post(path, headers=buyer_headers, json={}).json()
    fake_gateway.approve(checkout["provider_order_id"])
    assert paypal_client.post(path + "/capture", headers=buyer_headers, json={}).status_code == 200
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.get(PayPalCheckout, old_order["id"]).verified_at = datetime(2026, 1, 31, 12, tzinfo=UTC)
        assert db.get(OrderSalesCostSnapshot, old_order["id"]) is None
    row = details(paypal_client, market_headers)[0]
    assert row["estimated_profit"] is None and row["cost_snapshot"] is None
    assert "COST_SNAPSHOT_MISSING" in row["profit_unavailable_reasons"]
    new = paypal_client.post(
        "/api/v1/orders",
        headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
        json=cart,
    )
    assert new.status_code == 201
    with Session(paypal_client.app.state.engine) as db:
        assert db.get(OrderSalesCostSnapshot, new.json()["id"]).estimated_cost == "20.00"


def test_cost_selection_and_order_creation_freeze_one_consistent_revision(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    cost_selection,
    cart,
    payload,
):
    payload["costs"][0]["amount"] = "150.00"
    updated = market_client.post(
        order_source["path"] + "/analyses",
        headers=market_headers,
        json=payload,
    ).json()

    def choose():
        return selection(market_client, market_headers, order_source, 1, updated["id"])

    def create_order():
        return market_client.post(
            "/api/v1/orders",
            headers={**buyer_headers, "Idempotency-Key": str(uuid4())},
            json=cart,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        chosen, created = pool.submit(choose), pool.submit(create_order)
        selected, order = chosen.result(), created.result()
    assert selected.status_code == 200 and order.status_code == 201
    with Session(market_client.app.state.engine) as db:
        saved = db.get(OrderSalesCostSnapshot, order.json()["id"])
        item = saved.details["items"][0]
        assert (
            item["selection_revision"],
            item["source"]["analysis_id"],
            saved.estimated_cost,
        ) in (
            (1, cost_selection["analysis_id"], "20.00"),
            (2, updated["id"], "40.00"),
        )


def test_summary_never_silently_truncates_and_details_remain_paginated(
    paypal_client,
    market_headers,
    captured_sale,
):
    with Session(paypal_client.app.state.engine) as db, db.begin():
        original = db.get(Order, captured_sale["id"])
        # Seed verified synthetic receipts without provider calls to exercise the
        # actual query bound, not a mocked repository or a changed limit constant.
        for index in range(1000):
            order = Order(
                buyer_account_id=original.buyer_account_id,
                seller_account_id=original.seller_account_id,
                idempotency_key=str(uuid4()),
                request_hash="synthetic-report-fixture",
                status="pending_payment",
                created_at=original.created_at,
                expires_at=original.expires_at,
                subtotal_minor=3400,
                snapshot=original.snapshot,
            )
            db.add(order)
            db.flush()
            db.add(
                PayPalCheckout(
                    order_id=order.id,
                    merchant_id="ABCDEFGHIJKLM",
                    amount_minor=3400,
                    state="completed",
                    provider_order_id=f"SYNTHETICORDER{index:08}",
                    capture_id=f"SYNTHETICCAPTURE{index:08}",
                    provider_status="COMPLETED",
                    verified_at=datetime(2026, 1, 31, 12, tzinfo=UTC),
                    fee_minor=100,
                    net_minor=3300,
                )
            )
    response = paypal_client.get(SALES + PERIOD, headers=market_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REPORT_TOO_LARGE"
    response = paypal_client.get(
        SALES + "/orders" + PERIOD + "&limit=1&offset=1000",
        headers=market_headers,
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_openapi_has_only_private_reporting_and_strict_selection(paypal_client):
    schema = paypal_client.get("/openapi.json").json()
    for path in (SALES, SALES + "/orders", "/api/v1/products/{product_id}/sales-cost-basis"):
        for operation in schema["paths"][path].values():
            assert operation["security"] == [{"HTTPBearer": []}]
            assert {"401", "403", "409", "422"} <= set(operation["responses"])
    order_fields = schema["components"]["schemas"]["OrderResponse"]["properties"]
    assert "cost_snapshot" not in order_fields
    selection_model = schema["components"]["schemas"]["SelectCostBasis"]
    assert "analysis_id" in selection_model["required"]
    assert selection_model["additionalProperties"] is False
