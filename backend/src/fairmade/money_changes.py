"""Exact nullable amount changes shared by seller period and calendar reports."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from fairmade.pricing.schemas import Contract


class AmountChange(Contract):
    change: Decimal | None
    relative_change: Decimal | None


def displayed(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 60
        return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def difference(previous: Decimal | None, current: Decimal | None) -> AmountChange:
    if previous is None or current is None:
        return AmountChange(change=None, relative_change=None)
    with localcontext() as context:
        context.prec = 60
        delta = current - previous
        return AmountChange(
            change=displayed(delta),
            relative_change=displayed(delta / previous) if previous else None,
        )
