"""Small exact conversion registry. Never infer a loaf's weight or item equivalence."""

from decimal import Decimal

# Dimension families remain distinct even when both represent counts.
UNITS = {
    "g": ("mass", Decimal("1")),
    "kg": ("mass", Decimal("1000")),
    "egg": ("egg_count", Decimal("1")),
    "dozen": ("egg_count", Decimal("12")),
    "loaf": ("loaf_count", Decimal("1")),
    "item": ("item_count", Decimal("1")),
}


def named_unit_matches(product_type: str, unit: str) -> bool:
    if unit in ("egg", "dozen"):
        return product_type == "eggs"
    if unit == "loaf":
        return product_type == "sourdough"
    return True
