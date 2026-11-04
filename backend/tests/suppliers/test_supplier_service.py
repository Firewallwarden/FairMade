"""Deterministic usable yield, whole-package purchases and mandatory claim checks."""

from copy import deepcopy
from datetime import date
from decimal import Decimal, localcontext
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fairmade.quality.schemas import QualityLocks
from fairmade.suppliers.schemas import (
    SupplierComparisonRequest,
    SupplierQuoteCreate,
    SupplierQuoteSnapshot,
)
from fairmade.suppliers.service import compare_suppliers

AS_OF = date(2026, 1, 31)


def run(quote_body, rules_body, **changes):
    request = SupplierComparisonRequest(
        quote_ids=[uuid4()],
        expected_rule_revision=1,
        required_quantity={"value": "9", "unit": "kg"},
        **changes,
    )
    return compare_suppliers(
        request,
        [SupplierQuoteSnapshot(id=request.quote_ids[0], details=quote_body)],
        QualityLocks(revision=1, rules=rules_body["rules"]).rules,
        1,
        AS_OF,
    )


def test_whole_packages_yield_transport_and_surplus(quote_body, rules_body):
    result = run(quote_body, rules_body)
    row = result.rows[0]
    assert row.eligible_for_cost_comparison
    assert row.cost.model_dump() == {
        "packages_to_buy": 3,
        "merchandise_cost": Decimal("36.00"),
        "transport_cost": Decimal("4.00"),
        "purchase_cost": Decimal("40.00"),
        "usable_quantity": Decimal("12.000000"),
        "surplus_quantity": Decimal("3.000000"),
        "cost_per_usable_unit": Decimal("3.333333"),
    }
    assert result.lowest_purchase_cost == Decimal("40.00")
    assert result.lowest_cost_per_usable_unit == Decimal("3.333333")
    assert "INPUT_REQUIREMENTS_ONLY_PRODUCT_QUALITY_NOT_EVALUATED" in result.warnings
    assert "NOT_A_SUBSTITUTION_OR_FAIRNESS_RECOMMENDATION" in result.warnings


def test_bulk_minimum_changes_cash_outlay_and_unit_cost(quote_body, rules_body):
    quote_body["minimum_packages"] = 10
    cost = run(quote_body, rules_body).rows[0].cost
    assert cost.packages_to_buy == 10
    assert cost.purchase_cost == Decimal("124.00")
    assert cost.cost_per_usable_unit == Decimal("3.100000")


@pytest.mark.parametrize(("unit", "value"), [("g", "5000"), ("kg", "5")])
def test_exact_mass_conversion(quote_body, rules_body, unit, value):
    quote_body["package_quantity"] = {"value": value, "unit": unit}
    assert run(quote_body, rules_body).rows[0].cost.purchase_cost == Decimal("40.00")


def test_volume_conversion_and_caller_precision(quote_body, rules_body):
    quote_body["package_quantity"] = {"value": "500", "unit": "ml"}
    quote_body["usable_fraction"] = "1"
    request = SupplierComparisonRequest(
        quote_ids=[uuid4()],
        expected_rule_revision=1,
        required_quantity={"value": "1", "unit": "l"},
    )
    with localcontext() as context:
        context.prec = 3
        result = compare_suppliers(
            request,
            [SupplierQuoteSnapshot(id=request.quote_ids[0], details=quote_body)],
            QualityLocks(revision=1, rules=rules_body["rules"]).rules,
            1,
            AS_OF,
        )
    assert result.rows[0].cost.purchase_cost == Decimal("28.00")
    assert result.rows[0].cost.usable_quantity == Decimal("1.000000")
    assert result.rows[0].cost.cost_per_usable_unit == Decimal("28.000000")


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"observed_on": "2025-12-31"}, "STALE_QUOTE"),
        ({"observed_on": "2026-02-01"}, "FUTURE_QUOTE"),
        ({"observed_on": "2026-01-01", "valid_until": "2026-01-30"}, "EXPIRED_QUOTE"),
        ({"availability": "unknown"}, "AVAILABILITY_UNKNOWN"),
        ({"availability": "unavailable"}, "UNAVAILABLE"),
        ({"transport_cost": None}, "TRANSPORT_COST_UNKNOWN"),
        ({"maximum_packages": 2}, "INSUFFICIENT_AVAILABLE_PACKAGES"),
        ({"package_quantity": {"value": "1", "unit": "l"}}, "INCOMPATIBLE_UNITS"),
        ({"package_quantity": {"value": "0.000001", "unit": "g"}}, "PURCHASE_LIMIT_EXCEEDED"),
        ({"claims": {"organic": {"type": "boolean", "value": False}}}, "QUALITY_FAILED"),
        ({"claims": {}}, "QUALITY_UNKNOWN"),
        ({"claims": {"organic": {"type": "choice", "value": "yes"}}}, "QUALITY_UNKNOWN"),
    ],
)
def test_uncertain_or_failed_quotes_never_enter_cost_summary(
    quote_body, rules_body, changes, reason
):
    quote_body.update(changes)
    result = run(quote_body, rules_body)
    row = result.rows[0]
    assert reason in row.exclusion_reasons
    assert not row.eligible_for_cost_comparison
    assert result.eligible_count == 0
    assert result.lowest_purchase_cost is None
    assert result.lowest_cost_per_usable_unit is None
    assert "NO_ELIGIBLE_QUOTES" in result.warnings


def test_no_rules_is_not_a_quality_pass(quote_body, rules_body):
    rules_body["rules"] = []
    row = run(quote_body, rules_body).rows[0]
    assert row.quality.status == "not_evaluated"
    assert "QUALITY_NOT_EVALUATED" in row.exclusion_reasons


def test_numeric_requirements_do_not_infer_unit_equivalence(quote_body, rules_body):
    rules_body["rules"] = [
        {
            "key": "protein",
            "label": "Protein",
            "type": "numeric",
            "minimum": "12",
            "unit": "percent",
        }
    ]
    quote_body["claims"] = {"protein": {"type": "numeric", "value": "0.12", "unit": "fraction"}}
    row = run(quote_body, rules_body).rows[0]
    assert row.quality.checks[0].reason_code == "UNIT_MISMATCH"
    assert not row.eligible_for_cost_comparison


def test_cheaper_quality_failure_is_excluded(quote_body, rules_body):
    cheap = deepcopy(quote_body)
    cheap.update(package_price="0.01", claims={"organic": {"type": "boolean", "value": False}})
    ids = [uuid4(), uuid4()]
    request = SupplierComparisonRequest(
        quote_ids=ids,
        expected_rule_revision=1,
        required_quantity={"value": "9", "unit": "kg"},
    )
    result = compare_suppliers(
        request,
        [
            SupplierQuoteSnapshot(id=value, details=body)
            for value, body in zip(ids, [quote_body, cheap], strict=True)
        ],
        QualityLocks(revision=1, rules=rules_body["rules"]).rules,
        1,
        AS_OF,
    )
    assert result.eligible_count == 1
    assert result.lowest_purchase_cost == Decimal("40.00")
    assert "SOME_QUOTES_FAIL_MANDATORY_REQUIREMENTS" in result.warnings


def test_freshness_and_expiry_boundaries_are_inclusive(quote_body, rules_body):
    quote_body.update(observed_on="2026-01-01", valid_until="2026-01-31")
    assert run(quote_body, rules_body).eligible_count == 1


def test_exact_package_boundary_does_not_buy_extra(quote_body, rules_body):
    quote_body["package_quantity"] = {"value": "3", "unit": "kg"}
    quote_body["usable_fraction"] = "1"
    assert run(quote_body, rules_body).rows[0].cost.packages_to_buy == 3


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("package_price", 12.0),
        ("package_price", "-1"),
        ("package_price", "1.001"),
        ("package_price", "NaN"),
        ("transport_cost", 0),
        ("usable_fraction", "0"),
        ("usable_fraction", "1.000001"),
        ("usable_fraction", 0.8),
        ("minimum_packages", True),
        ("minimum_packages", "2"),
        ("maximum_packages", 0),
        ("availability", "verified"),
        ("observed_on", "2026-02-01"),
        ("valid_until", "2026-01-01"),
        ("package_quantity", {"value": "1.5", "unit": "item"}),
        ("package_quantity", {"value": "1", "unit": "lb"}),
        (
            "claims",
            {
                " organic ": {"type": "boolean", "value": True},
                "organic": {"type": "boolean", "value": False},
            },
        ),
        ("verified", True),
    ],
)
def test_rejects_ambiguous_or_invalid_quote_inputs(quote_body, key, value):
    quote_body[key] = value
    with pytest.raises(ValidationError):
        SupplierQuoteCreate.model_validate(quote_body)


def test_free_quote_requires_explicit_zero_transport(quote_body, rules_body):
    quote_body.update(package_price="0.00", transport_cost="0.00")
    result = run(quote_body, rules_body)
    assert result.eligible_count == 1
    assert result.lowest_purchase_cost == 0
