"""Small exact conversion registry. Never infer a loaf's weight or item equivalence."""

from fairmade.units import UNITS as UNITS


def named_unit_matches(product_type: str, unit: str) -> bool:
    if unit in ("egg", "dozen"):
        return product_type == "eggs"
    if unit == "loaf":
        return product_type == "sourdough"
    return True
