"""Exact dimension conversion and display rounding, independent of HTTP/storage."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from fairmade.unit_pricing.schemas import SellingQuantity, StandardUnitPrice
from fairmade.units import UNITS

REFERENCE_UNITS = {
    "mass": ("kg", Decimal("1000")),
    "volume": ("l", Decimal("1000")),
    "egg_count": ("egg", Decimal("1")),
    "loaf_count": ("loaf", Decimal("1")),
    "item_count": ("item", Decimal("1")),
}


def normalized_quantity(quantity: SellingQuantity) -> tuple[str, Decimal]:
    """Return base dimension and amount; never infer mass, density or count equivalence."""
    family, factor = UNITS[quantity.unit]
    with localcontext() as context:
        context.prec = 60
        return family, quantity.value * factor


def calculate(price: Decimal, quantity: SellingQuantity) -> StandardUnitPrice:
    if not price.is_finite() or price < 0:
        raise ValueError("Price must be finite and nonnegative")
    family, base_amount = normalized_quantity(quantity)
    reference_unit, reference_factor = REFERENCE_UNITS[family]
    with localcontext() as context:
        context.prec = 60
        exact = price * reference_factor / base_amount
        rounded = exact.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    below_precision = exact > 0 and rounded == 0
    return StandardUnitPrice(
        status="below_display_precision" if below_precision else "calculated",
        amount=None if below_precision else rounded,
        reference_unit=reference_unit,
    )
