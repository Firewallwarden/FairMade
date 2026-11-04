"""Production-cost rounding, coverage gaps and refund-aware estimates."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from uuid import uuid4

import pytest

from fairmade.sales.costing import cost_source, total_production_cost
from fairmade.sales.records import SaleRecord
from fairmade.sales.service import order_result, summarize

NOW = datetime(2026, 1, 31, 12, tzinfo=UTC)


def record(**changes):
    values = {
        "order_id": str(uuid4()),
        "created_at": NOW,
        "captured_at": NOW,
        "gross_minor": 2000,
        "fee_minor": 100,
        "net_minor": 1900,
        "refund_state": None,
        "refund_minor": None,
        "refund_verified_at": None,
        "cost_status": "available",
        "cost_total": "14.00",
    }
    values.update(changes)
    return SaleRecord(**values)


def summary(records):
    return summarize(records, date(2026, 1, 1), date(2026, 2, 1), NOW)


def test_profit_is_after_production_cost_and_verified_fee():
    row = order_result(record())
    assert row.gross_sales == Decimal("20.00")
    assert row.processing_fee == Decimal("1.00")
    assert row.after_refunds_and_fee == Decimal("19.00")
    assert row.estimated_production_cost == Decimal("14.00")
    assert row.estimated_profit == Decimal("5.00")
    assert row.estimated_margin == Decimal("0.250000")
    assert row.profit_unavailable_reasons == []
    assert row.fee_basis == "provider_fee"
    assert "SANDBOX_SHARED_MERCHANT_NOT_SELLER_PAYOUTS" in row.warnings


def test_full_refund_retains_production_costs_and_original_fee():
    row = order_result(record(refund_state="refunded", refund_minor=2000, refund_verified_at=NOW))
    assert row.completed_refunds == Decimal("20.00")
    assert row.after_refunds_and_fee == Decimal("-1.00")
    assert row.estimated_profit == Decimal("-15.00")
    assert row.estimated_margin is None


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"fee_minor": None, "net_minor": None}, "PROCESSING_FEE_UNAVAILABLE"),
        ({"cost_status": None, "cost_total": None}, "COST_SNAPSHOT_MISSING"),
        ({"cost_status": "unavailable", "cost_total": None}, "COST_BASIS_UNAVAILABLE"),
        ({"refund_state": "refund_pending"}, "REFUND_UNRESOLVED"),
        ({"refund_state": "needs_review"}, "REFUND_UNRESOLVED"),
    ],
)
def test_unknowns_do_not_become_zero_cost_or_profit(changes, reason):
    row = order_result(record(**changes))
    assert row.estimated_profit is None
    assert reason in row.profit_unavailable_reasons
    total = summary([record(), record(**changes)])
    assert total.estimated_profit is None
    assert total.covered_sales_count == 1
    assert total.covered_estimated_profit == Decimal("5.00")
    assert "PROFIT_COVERAGE_INCOMPLETE" in total.warnings


def test_verified_net_can_supply_the_missing_fee():
    row = order_result(record(fee_minor=None))
    assert row.processing_fee == Decimal("1.00")
    assert row.fee_basis == "derived_from_provider_net"
    assert row.estimated_profit == Decimal("5.00")


@pytest.mark.parametrize("state", ["requested", "denied", "failed"])
def test_uncompleted_refunds_are_not_deducted(state):
    row = order_result(record(refund_state=state, refund_minor=2000))
    assert row.completed_refunds == 0
    assert row.estimated_profit == Decimal("5.00")
    if state == "requested":
        assert "OPEN_REFUND_REQUEST_NOT_DEDUCTED" in row.warnings


def test_empty_period_and_explicit_zero_cost():
    empty = summary([])
    assert empty.sales_count == 0
    assert empty.estimated_profit == Decimal("0.00")
    assert empty.estimated_margin is None
    free_cost = order_result(record(cost_total="0.00"))
    assert free_cost.estimated_profit == Decimal("19.00")


def test_summary_has_full_counts_and_partial_known_fee_total():
    total = summary(
        [
            record(),
            record(fee_minor=None, net_minor=None),
            record(cost_status=None, cost_total=None),
            record(refund_state="refund_pending"),
        ]
    )
    assert total.sales_count == 4
    assert total.gross_sales == Decimal("80.00")
    assert total.known_processing_fees == Decimal("3.00")
    assert total.known_estimated_production_costs == Decimal("42.00")
    assert total.estimated_margin is None
    assert total.missing_fee_count == 1
    assert total.missing_cost_count == 1
    assert total.unresolved_refund_count == 1
    assert total.covered_sales_count == 1


def test_large_estimates_and_caller_precision_remain_exact():
    value = record(cost_total="2000000000000000000000000.01")
    with localcontext() as context:
        context.prec = 3
        total = summary([value, replace(value, order_id=str(uuid4()))])
    assert total.gross_sales == Decimal("40.00")
    assert total.estimated_profit == Decimal("-3999999999999999999999962.02")


def test_snapshot_uses_exact_batch_ratio_and_rounds_only_once():
    source = {"batch_production_cost": "1", "sellable_units": 3}
    items = [{"source": source, "quantity": 1, "unavailable_reason": None}] * 3
    with localcontext() as context:
        context.prec = 3
        assert total_production_cost(items) == Decimal("1.00")
    # Multiplying a six-decimal displayed unit cost would instead give 9999.99.
    bulk = [{"source": source, "quantity": 10_000, "unavailable_reason": None} for _ in range(3)]
    assert total_production_cost(bulk) == Decimal("10000.00")
    assert total_production_cost(
        [
            {
                "source": {"batch_production_cost": "0.01", "sellable_units": 2},
                "quantity": 1,
                "unavailable_reason": None,
            }
        ]
    ) == Decimal("0.01")


def test_any_missing_line_makes_whole_order_cost_unavailable():
    assert (
        total_production_cost(
            [
                {
                    "source": None,
                    "quantity": 1,
                    "unavailable_reason": "COST_BASIS_NOT_SELECTED",
                }
            ]
        )
        is None
    )


def test_production_cost_snapshot_ignores_modeled_payment_fees(payload):
    product = {"selling_unit": "loaf", "product_type": "sourdough"}
    source = cost_source(payload, product, str(uuid4()), NOW.isoformat())
    assert Decimal(source["batch_production_cost"]) == Decimal("100")
    assert source["sellable_units"] == 10
    payload["payment_fees"].update(rate="0.5", fixed_per_order="100")
    source2 = cost_source(payload, product, str(uuid4()), NOW.isoformat())
    assert source["batch_production_cost"] == source2["batch_production_cost"]


def test_snapshot_preserves_sub_micro_costs_instead_of_rounded_analysis_output(payload):
    payload.update(
        sellable_units=1,
        costs=[],
        labor=[{"label": "Synthetic", "hours": "0.000001", "hourly_rate": "0.000001"}],
    )
    source = cost_source(
        payload, {"selling_unit": "item", "product_type": "other"}, str(uuid4()), NOW.isoformat()
    )
    assert Decimal(source["batch_production_cost"]) == Decimal("0.000000000001")
    assert source["display_unit_cost"] == "0.000000"
