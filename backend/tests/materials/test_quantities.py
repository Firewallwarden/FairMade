"""Independent exact-unit and boundary checks for the quantity-only ledger."""

from decimal import Decimal, localcontext

import pytest

from fairmade.materials.quantities import (
    MAX_MICROS,
    SCALE,
    QuantityError,
    display,
    next_balance,
    normalize,
)


@pytest.mark.parametrize(
    ("quantity", "unit", "canonical", "expected"),
    [
        ("1.234567", "g", "g", 1234567),
        ("0.000001", "kg", "g", 1000),
        ("1.25", "kg", "g", 1250000000),
        ("2.5", "l", "ml", 2500000000),
        ("0.000001", "ml", "ml", 1),
        ("2", "item", "item", 2000000),
    ],
)
def test_exact_conversions_and_display_are_context_independent(quantity, unit, canonical, expected):
    with localcontext() as context:
        context.prec = 5
        assert normalize(Decimal(quantity), unit, canonical) == expected
        result = display(expected)
    assert result == Decimal(expected) / SCALE
    assert result.as_tuple().exponent == -6


@pytest.mark.parametrize(
    ("quantity", "unit", "canonical", "code"),
    [
        ("1", "g", "ml", "UNIT_MISMATCH"),
        ("1", "item", "g", "UNIT_MISMATCH"),
        ("0.5", "item", "item", "WHOLE_ITEMS_REQUIRED"),
        ("0.0000001", "g", "g", "QUANTITY_PRECISION"),
        ("1000000000", "kg", "g", "QUANTITY_LIMIT"),
    ],
)
def test_incompatible_fractional_and_out_of_range_quantities_fail(quantity, unit, canonical, code):
    with pytest.raises(QuantityError) as exc:
        normalize(Decimal(quantity), unit, canonical)
    assert exc.value.code == code


def test_receipt_usage_waste_and_physical_count_semantics():
    assert next_balance(5 * SCALE, 2 * SCALE, "receipt") == 7 * SCALE
    assert next_balance(5 * SCALE, 2 * SCALE, "usage") == 3 * SCALE
    assert next_balance(5 * SCALE, 2 * SCALE, "waste") == 3 * SCALE
    assert next_balance(5 * SCALE, 2 * SCALE, "adjustment") == 2 * SCALE
    assert next_balance(5 * SCALE, 0, "adjustment") == 0
    assert next_balance(5 * SCALE, 5 * SCALE, "adjustment") == 5 * SCALE


@pytest.mark.parametrize(
    ("before", "amount", "kind", "code"),
    [
        (SCALE, 2 * SCALE, "usage", "INSUFFICIENT_MATERIAL"),
        (SCALE, 2 * SCALE, "waste", "INSUFFICIENT_MATERIAL"),
        (MAX_MICROS, 1, "receipt", "QUANTITY_LIMIT"),
        (0, 0, "receipt", "POSITIVE_QUANTITY_REQUIRED"),
        (0, -1, "receipt", "QUANTITY_LIMIT"),
    ],
)
def test_balance_boundaries_reject_invalid_changes(before, amount, kind, code):
    with pytest.raises(QuantityError) as exc:
        next_balance(before, amount, kind)
    assert exc.value.code == code
