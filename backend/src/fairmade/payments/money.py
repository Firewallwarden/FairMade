"""Exact parsing of provider-reported USD amounts, without float coercion."""

import re
from decimal import Decimal, localcontext

AMOUNT = re.compile(r"[0-9]{1,10}(?:\.[0-9]{1,2})?")


def parse_usd_minor(value: dict) -> int:
    if not isinstance(value, dict) or value.get("currency_code") != "USD":
        raise ValueError("Expected USD money")
    amount = value.get("value")
    if not isinstance(amount, str) or not AMOUNT.fullmatch(amount):
        raise ValueError("Expected an exact USD decimal string")
    with localcontext() as context:
        context.prec = 40
        return int(Decimal(amount) * 100)
