from decimal import Decimal, localcontext

import pytest

from fairmade.pricing.schemas import PricingRequest
from fairmade.pricing.service import calculate


def test_economics_and_api_contract(client, payload):
    response = client.post("/api/v1/pricing/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["calculation_version"] == "production-economics-v1"
    assert data["basis"] == "seller_supplied_unverified"
    assert data["costs"]["batch_total"] == "100.000000"
    assert data["costs"]["labor_total"] == "30.000000"
    assert data["costs"]["unit_cost"] == "10.000000"
    assert data["fixed_fee_per_unit"] == "0.250000"
    assert data["break_even_price"] == "10.57"
    assert data["sustainable_price_range"] == {"minimum": "13.32", "maximum": "15.30"}
    loss, profit = data["scenarios"]
    assert loss["below_break_even"] is True
    assert loss["profit_per_unit"] == "-0.550000"
    assert profit["processing_fee_per_unit"] == "0.700000"
    assert profit["profit_per_unit"] == "4.300000"
    assert profit["batch_profit"] == "43.000000"
    assert profit["margin"] == "0.286667"
    assert profit["markup"] == "0.500000"
    assert profit["below_target_margin"] is False
    assert {item["code"] for item in data["warnings"]} == {
        "UNVERIFIED_INPUTS",
        "MARKET_NOT_EVALUATED",
        "QUALITY_NOT_EVALUATED",
        "UNSUSTAINABLE_PRICE",
    }


def test_waste_reduces_sellable_yield_without_removing_consumed_cost(payload):
    full = calculate(PricingRequest.model_validate(payload))
    payload["sellable_units"] = 5
    reduced = calculate(PricingRequest.model_validate(payload))
    assert reduced.costs.batch_total == full.costs.batch_total
    assert reduced.costs.unit_cost == full.costs.unit_cost * 2


def test_fixed_fee_is_allocated_per_order_not_per_batch(payload):
    payload["payment_fees"]["units_per_order"] = 1
    result = calculate(PricingRequest.model_validate(payload))
    assert result.fixed_fee_per_unit == Decimal("0.5")
    assert result.scenarios[1].processing_fee_per_unit == Decimal("0.95")


@pytest.mark.parametrize("yield_count", [1, 3, 7, 1000000])
def test_ceiling_price_never_loses_money_or_misses_target(payload, yield_count):
    payload["sellable_units"] = yield_count
    payload["target_margin"] = {"minimum": "0", "maximum": "0.70"}
    request = PricingRequest.model_validate(payload)
    result = calculate(request)
    unit_cost = Decimal(100) / yield_count
    fixed = Decimal("0.25")
    for price, margin in (
        (result.break_even_price, Decimal(0)),
        (result.sustainable_price_range.maximum, Decimal("0.70")),
    ):
        assert price * (1 - Decimal("0.03") - margin) >= unit_cost + fixed
        assert (price - Decimal("0.01")) * (1 - Decimal("0.03") - margin) < unit_cost + fixed


def test_no_premature_rounding_of_recurring_unit_cost(payload):
    payload["costs"] = [{"label": "Input", "category": "materials", "amount": "1"}]
    payload["labor"] = []
    payload["sellable_units"] = 3
    payload["payment_fees"] = {"rate": "0", "fixed_per_order": "0", "units_per_order": 1}
    payload["target_margin"] = {"minimum": "0", "maximum": "0"}
    result = calculate(PricingRequest.model_validate(payload))
    assert result.costs.unit_cost == Decimal("0.333333")
    assert result.break_even_price == Decimal("0.34")


def test_zero_price_and_free_inputs_have_no_undefined_ratios(payload):
    payload["costs"] = []
    payload["labor"] = []
    payload["proposed_prices"] = ["0", "1"]
    result = calculate(PricingRequest.model_validate(payload))
    assert result.scenarios[0].margin is None
    assert result.scenarios[0].markup is None
    assert result.scenarios[0].below_target_margin is True
    assert result.scenarios[1].markup is None
    assert {w.code for w in result.warnings} >= {"NO_LABOR_COST", "NO_OVERHEAD_COST"}


def test_fees_can_be_explicitly_zero_and_prices_are_not_required(payload):
    payload["payment_fees"] = {"rate": "0", "fixed_per_order": "0", "units_per_order": 1}
    del payload["proposed_prices"]
    result = calculate(PricingRequest.model_validate(payload))
    assert result.break_even_price == Decimal("10")
    assert result.sustainable_price_range.minimum == Decimal("12.50")
    assert result.scenarios == []


def test_decimal_calculation_does_not_depend_on_callers_precision(payload):
    request = PricingRequest.model_validate(payload)
    expected = calculate(request)
    with localcontext() as context:
        context.prec = 6
        assert calculate(request) == expected


@pytest.mark.parametrize(
    "path,value",
    [
        (("sellable_units",), 0),
        (("sellable_units",), -1),
        (("sellable_units",), True),
        (("sellable_units",), 1.5),
        (("sellable_units",), 1000001),
        (("currency",), "EUR"),
        (("costs", 0, "amount"), "-0.01"),
        (("costs", 0, "amount"), "NaN"),
        (("costs", 0, "amount"), "Infinity"),
        (("costs", 0, "amount"), "1000000001"),
        (("costs", 0, "amount"), "0.0000001"),
        (("costs", 0, "label"), "   "),
        (("costs", 0, "category"), "unknown"),
        (("labor", 0, "hours"), "-1"),
        (("labor", 0, "hourly_rate"), "-1"),
        (("payment_fees", "rate"), "1"),
        (("payment_fees", "rate"), "-0.01"),
        (("payment_fees", "fixed_per_order"), "-1"),
        (("payment_fees", "units_per_order"), 0),
        (("target_margin", "minimum"), "0.31"),
        (("target_margin", "maximum"), "0.97"),
        (("target_margin", "maximum"), "1"),
        (("proposed_prices", 0), "-1"),
        (("costs", 0, "unexpected"), "value"),
        (("unexpected",), "value"),
    ],
)
def test_invalid_economics_returns_422(client, payload, path, value):
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert client.post("/api/v1/pricing/analyze", json=payload).status_code == 422


@pytest.mark.parametrize("field", ["currency", "costs", "labor", "payment_fees", "target_margin"])
def test_required_inputs_are_not_silently_assumed(client, payload, field):
    del payload[field]
    assert client.post("/api/v1/pricing/analyze", json=payload).status_code == 422


@pytest.mark.parametrize("field,limit", [("costs", 200), ("labor", 100), ("proposed_prices", 50)])
def test_lists_are_bounded(client, payload, field, limit):
    payload[field] = [payload[field][0]] * (limit + 1)
    assert client.post("/api/v1/pricing/analyze", json=payload).status_code == 422


def test_health_and_openapi(client):
    assert client.get("/health").json() == {"status": "ok"}
    schema = client.get("/openapi.json").json()
    assert "/api/v1/pricing/analyze" in schema["paths"]
    assert "422" in schema["paths"]["/api/v1/pricing/analyze"]["post"]["responses"]
