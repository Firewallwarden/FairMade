"""Reported actual costs share exact arithmetic without pricing assumptions."""

import json
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from fairmade.production.costing import calculate_completed
from fairmade.production.schemas import ProductionRequest


def test_completed_bread_costs_and_yield(production_body):
    result = calculate_completed(ProductionRequest.model_validate(production_body))
    assert result.batch_total == Decimal("45.300000")
    assert result.labor_total == Decimal("30.000000")
    assert result.unit_cost == Decimal("4.530000")
    assert result.unsellable_units == 2
    assert result.yield_fraction == Decimal("0.833333")
    assert result.basis == "seller_reported_unverified"


def test_completed_egg_period_uses_explicit_output_basis():
    path = Path(__file__).parents[2] / "examples/production/eggs.json"
    request = ProductionRequest.model_validate(json.loads(path.read_text(encoding="utf-8")))
    result = calculate_completed(request)
    assert request.selling_unit == "dozen"
    assert result.batch_total == Decimal("58.000000")
    assert result.unit_cost == Decimal("2.416667")
    assert result.yield_fraction == Decimal("0.923077")


def test_zero_output_preserves_expenses_without_dividing_by_zero(production_body):
    production_body.update(total_units=0, sellable_units=0)
    result = calculate_completed(ProductionRequest.model_validate(production_body))
    assert result.batch_total == Decimal("45.300000")
    assert result.unit_cost is None and result.yield_fraction is None
    assert any("ZERO_SELLABLE_YIELD" in item for item in result.warnings)


def test_all_output_unsellable_has_zero_yield_but_unknown_unit_cost(production_body):
    production_body["sellable_units"] = 0
    result = calculate_completed(ProductionRequest.model_validate(production_body))
    assert result.unsellable_units == 12 and result.yield_fraction == 0
    assert result.unit_cost is None


def test_calculation_does_not_depend_on_ambient_decimal_context(production_body):
    request = ProductionRequest.model_validate(production_body)
    expected = calculate_completed(request)
    with localcontext() as context:
        context.prec = 5
        assert calculate_completed(request) == expected


def test_missing_cost_categories_remain_visible_as_gaps(production_body):
    production_body.update(costs=[], labor=[])
    result = calculate_completed(ProductionRequest.model_validate(production_body))
    assert result.batch_total == 0
    assert all(
        any(code in item for item in result.warnings)
        for code in ("NO_LABOR_COST", "NO_OVERHEAD_COST", "NO_MATERIAL_COST")
    )


@pytest.mark.parametrize("value", [10, True, "-1", "NaN", "0.0000001", "Infinity"])
def test_recorded_money_rejects_numbers_and_invalid_decimal_strings(production_body, value):
    production_body["costs"][0]["amount"] = value
    with pytest.raises(ValidationError):
        ProductionRequest.model_validate(production_body)
