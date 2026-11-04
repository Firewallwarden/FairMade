"""Exact quantity dimensions; mass, volume and named counts never mix."""

from decimal import Decimal

UNITS = {
    "g": ("mass", Decimal("1")),
    "kg": ("mass", Decimal("1000")),
    "ml": ("volume", Decimal("1")),
    "l": ("volume", Decimal("1000")),
    "egg": ("egg_count", Decimal("1")),
    "dozen": ("egg_count", Decimal("12")),
    "loaf": ("loaf_count", Decimal("1")),
    "item": ("item_count", Decimal("1")),
}
