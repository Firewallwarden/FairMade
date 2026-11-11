"""A qualitative model view; exact numerical evidence never needs model transcription."""

import re
from decimal import Decimal

from fairmade.assistants.expenses import expense_context
from fairmade.assistants.history import history_context
from fairmade.assistants.schemas import Evidence
from fairmade.assistants.supplier_explanations import supplier_context
from fairmade.baskets.integration import context as basket_context
from fairmade.personalization.integration import context as personalization_context

DIGITS = re.compile(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?")
QUESTION_AMOUNTS = re.compile(r"(?:USD\s*|\$)?[-+]?\d+(?:,\d{3})*(?:\.\d+)?")


def qualitative(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return "[exact value in backend facts]"
    if isinstance(value, str):
        return DIGITS.sub("[exact value in backend facts]", value)
    if isinstance(value, list):
        return [qualitative(item) for item in value]
    if isinstance(value, dict):
        return {
            key: qualitative(item)
            for key, item in value.items()
            if not key.endswith(("_id", "_hash", "_at"))
        }
    raise TypeError("Evidence must be JSON data")


def model_evidence(evidence: list[Evidence]) -> list[dict]:
    result = []
    for fact in evidence:
        data = history_context(fact)
        if data is None:
            data = expense_context(fact)
        if data is None:
            data = supplier_context(fact)
        if data is None:
            data = personalization_context(fact)
        if data is None:
            data = basket_context(fact)
        if data is None:
            data = fact.data
        if fact.title == "Selected saved production economics":
            costs = data["result"]["costs"]
            data = {
                "cost_categories_with_recorded_cost": [
                    category
                    for category, amount in costs["category_totals"].items()
                    if Decimal(amount) > 0
                ],
                "labor_cost_included": Decimal(costs["labor_total"]) > 0,
                "range_basis": "Seller-selected profit margin targets, not a fairness finding.",
                "warnings": [
                    warning
                    for warning in data["result"]["warnings"]
                    if warning["code"] != "UNSUSTAINABLE_PRICE"
                ],
                "assumptions": data["result"]["assumptions"],
            }
        elif fact.title == "Currently approved public listing and Passport":
            listing = data["payload"]
            passport = data["passport"]["payload"]
            costs = passport.get("costs") or {}
            data = {
                "product": listing["product"],
                "price_recorded": True,
                "declared_contents_recorded": listing.get("selling_quantity") is not None,
                "standard_unit_price_status": (
                    listing["unit_price"]["status"] if listing.get("unit_price") else "unknown"
                ),
                "disclosed_cost_categories": list(costs.get("category_costs_per_unit", {})),
                "labor_cost_disclosed": costs.get("labor_per_unit") is not None,
                "unit_cost_disclosed": costs.get("unit_cost") is not None,
                "quality_requirements": passport.get("quality_requirements"),
                "quality_summary": passport.get("quality_summary"),
                "market_context_disclosed": passport.get("market_context") is not None,
                "policy": (
                    "Exact selling and comparison prices appear in calculated facts. "
                    "Undisclosed costs might OR might not be included in the seller's price; "
                    "we cannot determine this. Never say the price excludes undisclosed costs. "
                    "Quality claims remain seller-reported and unverified."
                ),
            }
        elif fact.title == "Deterministic requested price scenarios":
            data = {
                "policy": (
                    "The calculated facts state exact profit, margin and break-even outcomes. "
                    "Explain assumptions only; do not infer or restate numerical outcomes."
                ),
                "assumptions": data["assumptions"],
            }
        elif fact.title == "Deterministic public unit-price comparisons":
            data = {
                "pairs": [
                    {
                        "compatible_price_basis": pair["compatible_price_basis"],
                        "policy": (
                            "The calculated facts show exact prices and differences. "
                            "Explain comparability and limitations, not price outcomes."
                        ),
                    }
                    for pair in data["pairs"]
                ]
            }
        result.append(
            {
                "key": fact.key,
                "title": fact.title,
                "basis": fact.basis,
                "data": qualitative(data),
            }
        )
    return result
