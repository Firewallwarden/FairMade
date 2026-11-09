"""Independent allocation examples, exact conversions and rounding boundaries."""

import json
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from fairmade.pricing.service import calculate
from fairmade.recipes.costing import CostLimitError, compile_recipe
from fairmade.recipes.schemas import RecipeData

EXAMPLES = Path(__file__).parents[2] / "examples" / "recipes"


def test_bread_purchase_allocations_feed_existing_economics(recipe_body):
    inputs, allocations = compile_recipe(RecipeData.model_validate(recipe_body))
    assert [line.allocated_cost for line in allocations.ingredients] == [
        Decimal("10.000000"),
        Decimal("0.300000"),
    ]
    assert allocations.materials_total == Decimal("10.300000")
    result = calculate(inputs)
    assert result.costs.batch_total == Decimal("45.300000")
    assert result.costs.unit_cost == Decimal("4.530000")
    assert result.break_even_price == Decimal("4.98")
    assert result.sustainable_price_range.minimum == Decimal("6.28")
    assert "QUALITY_NOT_EVALUATED" in {warning.code for warning in result.warnings}
    assert result.scenarios[0].below_break_even


def test_egg_feed_allocation_and_sellable_dozen_basis():
    content = json.loads((EXAMPLES / "eggs.json").read_text(encoding="utf-8"))
    inputs, allocations = compile_recipe(RecipeData.model_validate(content))
    assert allocations.materials_total == Decimal("18.000000")
    assert calculate(inputs).costs.batch_total == Decimal("58.000000")
    assert calculate(inputs).costs.unit_cost == Decimal("2.416667")


def test_allocation_rounding_is_once_per_line_and_context_independent(recipe_body):
    body = deepcopy(recipe_body)
    body["ingredients"] = [
        {
            "label": "Third of a package",
            "quantity": {"value": "1", "unit": "item"},
            "purchase_quantity": {"value": "3", "unit": "item"},
            "purchase_cost": "1",
            "cost_recorded_on": "2026-11-01",
        },
        {
            "label": "Half a micro dollar",
            "quantity": {"value": "1", "unit": "g"},
            "purchase_quantity": {"value": "2", "unit": "g"},
            "purchase_cost": "0.000001",
            "cost_recorded_on": "2026-11-01",
        },
    ]
    recipe = RecipeData.model_validate(body)
    expected = compile_recipe(recipe)
    with localcontext() as context:
        context.prec = 7
        assert compile_recipe(recipe) == expected
    assert expected[1].materials_total == Decimal("0.333334")


def test_sub_micro_allocations_are_disclosed(recipe_body):
    recipe_body["ingredients"][0]["quantity"]["value"] = "0.000001"
    recipe_body["ingredients"][0]["purchase_cost"] = "0.01"
    _, result = compile_recipe(RecipeData.model_validate(recipe_body))
    assert any("rounded to zero" in warning for warning in result.warnings)


def test_zero_cost_is_explicitly_allowed(recipe_body):
    recipe_body["ingredients"][0]["purchase_cost"] = "0"
    _, result = compile_recipe(RecipeData.model_validate(recipe_body))
    assert result.ingredients[0].allocated_cost == 0


def test_unrepresentable_allocation_is_rejected(recipe_body):
    recipe_body["ingredients"][0]["quantity"]["value"] = "1000000000"
    recipe_body["ingredients"][0]["purchase_quantity"]["value"] = "0.000001"
    recipe_body["ingredients"][0]["purchase_cost"] = "1000000000"
    with pytest.raises(CostLimitError):
        compile_recipe(RecipeData.model_validate(recipe_body))


@pytest.mark.parametrize(
    "change",
    [
        {"quantity": {"value": "0", "unit": "g"}},
        {"quantity": {"value": "-1", "unit": "g"}},
        {"quantity": {"value": "NaN", "unit": "g"}},
        {"quantity": {"value": 12.5, "unit": "g"}},
        {"quantity": {"value": "0.0000001", "unit": "g"}},
        {"quantity": {"value": "1", "unit": "cup"}},
        {"quantity": {"value": "1.5", "unit": "item"}},
        {"purchase_quantity": {"value": "0", "unit": "kg"}},
        {"purchase_quantity": {"value": "1", "unit": "l"}},
        {"purchase_cost": "-1"},
        {"purchase_cost": 10},
        {"purchase_cost": "Infinity"},
        {"supplier_quote_id": "Not accepted"},
    ],
)
def test_invalid_quantities_prices_and_source_fields_are_rejected(recipe_body, change):
    recipe_body["ingredients"][0].update(change)
    with pytest.raises(ValidationError):
        RecipeData.model_validate(recipe_body)
