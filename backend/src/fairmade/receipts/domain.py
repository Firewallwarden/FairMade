"""Exact receipt review rules; no AI calculations or implicit stock/cost effects."""

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, localcontext


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def preview_digest(identifier, revision: int, details: dict) -> str:
    return digest({"id": str(identifier), "revision": revision, "details": details})


def initial_details(extracted: dict) -> dict:
    text = extracted.get("date_text") or ""
    try:
        purchased_on = (
            date.fromisoformat(text).isoformat()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text)
            else None
        )
    except ValueError:
        purchased_on = None
    return {
        **{key: value for key, value in extracted.items() if key != "date_text"},
        "purchased_on": purchased_on,
        "category": "other",
    }


def review_issues(details: dict) -> list[str]:
    issues = []
    for key in ("merchant", "purchased_on", "currency", "total"):
        if details.get(key) is None:
            issues.append("MISSING_" + key.upper())
    total = Decimal(details["total"]) if details.get("total") is not None else None
    if total is not None and total <= 0:
        issues.append("TOTAL_MUST_BE_POSITIVE")
    subtotal = Decimal(details["subtotal"]) if details.get("subtotal") is not None else None
    tax = Decimal(details["tax"]) if details.get("tax") is not None else None
    items = details.get("items", [])
    with localcontext() as context:
        context.prec = 40
        if total is not None and subtotal is not None and subtotal > total:
            issues.append("SUBTOTAL_EXCEEDS_TOTAL")
        if (
            total is not None
            and subtotal is not None
            and tax is not None
            and subtotal + tax != total
        ):
            issues.append("TOTAL_MISMATCH")
        if items and all(item["line_total"] is not None for item in items):
            item_sum = sum((Decimal(item["line_total"]) for item in items), Decimal(0))
            basis = (
                subtotal
                if subtotal is not None
                else (total - tax if total is not None and tax is not None else None)
            )
            if basis is not None and item_sum != basis:
                issues.append("ITEM_TOTAL_MISMATCH")
    return issues


def validate_extraction(extracted: dict, text: str) -> bool:
    folded = " ".join(text.casefold().split())
    for value in [extracted["merchant"], extracted["date_text"]] + [
        item["description"] for item in extracted["items"]
    ]:
        if value is not None and " ".join(value.casefold().split()) not in folded:
            return False
    amounts = {
        Decimal(token.replace(",", ""))
        for token in re.findall(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d{1,2})?(?![\w.])", text)
    }
    values = [extracted[key] for key in ("subtotal", "tax", "total")] + [
        item["line_total"] for item in extracted["items"]
    ]
    if any(value is not None and Decimal(value) not in amounts for value in values):
        return False
    return extracted["currency"] is None or bool(re.search(r"\bUSD\b|US\$", text, re.I))
