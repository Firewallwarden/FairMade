"""Exact fixed-point stock changes: base grams, milliliters or whole items."""

from decimal import Decimal, localcontext

from fairmade.units import UNITS

SCALE = 1_000_000
MAX_MICROS = 1_000_000_000 * SCALE


class QuantityError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def normalize(quantity: Decimal, input_unit: str, canonical_unit: str) -> int:
    if UNITS[input_unit][0] != UNITS[canonical_unit][0]:
        raise QuantityError("UNIT_MISMATCH", "Quantity has an incompatible material unit.")
    with localcontext() as context:
        context.prec = 50
        micros = quantity * UNITS[input_unit][1] * SCALE
        if micros != micros.to_integral_value():
            raise QuantityError("QUANTITY_PRECISION", "Quantity cannot be stored exactly.")
        if not 0 <= micros <= MAX_MICROS:
            raise QuantityError("QUANTITY_LIMIT", "Quantity exceeds the normalized stock limit.")
        if canonical_unit == "item" and micros % SCALE:
            raise QuantityError("WHOLE_ITEMS_REQUIRED", "Item counts must be whole numbers.")
        return int(micros)


def next_balance(before: int, amount: int, kind: str) -> int:
    if not 0 <= before <= MAX_MICROS or not 0 <= amount <= MAX_MICROS:
        raise QuantityError("QUANTITY_LIMIT", "Quantity exceeds the stock limit.")
    if kind != "adjustment" and amount == 0:
        raise QuantityError(
            "POSITIVE_QUANTITY_REQUIRED", "A positive movement quantity is required."
        )
    if kind == "receipt":
        after = before + amount
    elif kind in ("usage", "waste"):
        after = before - amount
    elif kind == "adjustment":
        after = amount
    else:
        raise ValueError("Unsupported movement kind")
    if after < 0:
        raise QuantityError("INSUFFICIENT_MATERIAL", "The movement would make stock negative.")
    if after > MAX_MICROS:
        raise QuantityError("QUANTITY_LIMIT", "The movement exceeds the stock balance limit.")
    return after


def display(micros: int) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return (Decimal(micros) / SCALE).quantize(Decimal("0.000001"))
