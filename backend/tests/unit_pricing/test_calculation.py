"""Exact compatible dimensions, whole counts and honest display precision."""

from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from fairmade.unit_pricing.schemas import SellingQuantity
from fairmade.unit_pricing.service import calculate, normalized_quantity


@pytest.mark.parametrize(
    "value,unit,price,reference,expected",
    [
        ("500", "g", "7.50", "kg", "15.000000"),
        ("0.5", "kg", "7.50", "kg", "15.000000"),
        ("750", "ml", "4.50", "l", "6.000000"),
        ("1.5", "l", "4.50", "l", "3.000000"),
        ("12", "egg", "4.80", "egg", "0.400000"),
        ("1", "dozen", "4.80", "egg", "0.400000"),
        ("0.5", "dozen", "2.40", "egg", "0.400000"),
        ("2", "loaf", "9.00", "loaf", "4.500000"),
        ("3", "item", "10.00", "item", "3.333333"),
        ("1", "item", "0", "item", "0.000000"),
        ("0.000001", "g", "1000000000", "kg", "1000000000000000000.000000"),
    ],
)
def test_exact_supported_quantities(value, unit, price, reference, expected):
    quantity = SellingQuantity(value=value, unit=unit)
    with localcontext() as context:
        context.prec = 2
        result = calculate(Decimal(price), quantity)
        assert context.prec == 2
    assert str(result.amount) == expected and result.reference_unit == reference
    assert result.reference_quantity == "1" and result.status == "calculated"
    assert result.basis == "seller_reported_unverified"


@pytest.mark.parametrize("value,unit", [("1000000000", "kg"), ("1000000000", "dozen")])
def test_positive_below_precision_never_looks_free(value, unit):
    quantity = SellingQuantity(value=value, unit=unit)
    result = calculate(Decimal("0.01"), quantity)
    assert result.status == "below_display_precision" and result.amount is None
    free = calculate(Decimal("0"), quantity)
    assert free.status == "calculated" and free.amount == 0


@pytest.mark.parametrize(
    "value,unit",
    [
        (1, "g"),
        (True, "item"),
        ("0", "g"),
        ("-1", "kg"),
        ("NaN", "ml"),
        ("Infinity", "l"),
        ("1000000001", "g"),
        ("0.0000001", "g"),
        ("1.5", "egg"),
        ("1.5", "loaf"),
        ("1.5", "item"),
        ("0.1", "dozen"),
        ("1", "lb"),
        ("0" * 65 + "1", "g"),
    ],
)
def test_invalid_quantities(value, unit):
    with pytest.raises(ValidationError):
        SellingQuantity(value=value, unit=unit)


def test_dimensions_do_not_imply_density_or_count_equivalence():
    def normalized(unit):
        return normalized_quantity(SellingQuantity(value="1", unit=unit))[0]

    assert len({normalized(unit) for unit in ("g", "ml", "egg", "loaf", "item")}) == 5
    assert normalized("kg") == normalized("g") and normalized("l") == normalized("ml")
    assert normalized("dozen") == normalized("egg")
    for value in ("-1", "NaN", "Infinity"):
        with pytest.raises(ValueError):
            calculate(Decimal(value), SellingQuantity(value="1", unit="item"))
