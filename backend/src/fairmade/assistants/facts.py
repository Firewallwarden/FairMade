"""Render exact numeric statements on the server; never ask an LLM to write arithmetic."""

from fairmade.assistants.history import history_statements
from fairmade.assistants.schemas import Evidence, Paragraph


def statements(evidence: list[Evidence]) -> list[Paragraph]:
    result: list[Paragraph] = []

    def add(fact: Evidence, text: str):
        result.append(Paragraph(text=text, evidence_keys=[fact.key]))

    for fact in evidence:
        result.extend(history_statements(fact))
        data = fact.data
        if fact.title == "Selected saved production economics":
            costs = data["result"]["costs"]
            unit = data["product_snapshot"]["selling_unit"]
            bounds = data["result"]["sustainable_price_range"]
            add(
                fact,
                (
                    f"Saved batch cost: USD {costs['batch_total']} for "
                    f"{data['sellable_units']} sellable units. "
                    f"Modeled cost per {unit}: USD {costs['unit_cost']}."
                ),
            )
            add(
                fact,
                (
                    f"Fee-aware modeled break-even: USD {data['result']['break_even_price']}. "
                    f"Range from seller-selected margin targets: USD {bounds['minimum']} "
                    f"to USD {bounds['maximum']} per {unit}. This is not a fairness verdict."
                ),
            )
        elif fact.title == "Deterministic requested price scenarios":
            for row in data["scenarios"]:
                state = "below" if row["below_break_even"] else "at or above"
                margin = row["margin"] if row["margin"] is not None else "undefined at zero revenue"
                markup = row["markup"] if row["markup"] is not None else "undefined at zero cost"
                target = "below" if row["below_target_margin"] else "at or above"
                add(
                    fact,
                    (
                        f"At USD {row['price']} per {data['selling_unit']}, "
                        f"modeled profit per unit is USD {row['profit_per_unit']} "
                        f"and batch profit is USD {row['batch_profit']}. "
                        f"Margin fraction: {margin}; markup fraction: {markup}. "
                        f"This scenario is {state} modeled break-even. "
                        f"It is {target} the seller's minimum target margin. "
                        "Batch profit assumes all sellable units sell."
                    ),
                )
        elif fact.title == "Currently approved public listing and Passport":
            payload = data["payload"]
            unit = payload["product"]["selling_unit"]
            add(
                fact,
                (
                    f"Approved listing price for {payload['product']['title']}: "
                    f"USD {payload['price']['amount']} per {unit}. "
                    "Approval records the seller's disclosure, not independent verification."
                ),
            )
            normalized = payload.get("unit_price")
            if normalized and normalized["status"] == "calculated":
                add(
                    fact,
                    (
                        f"Standardized display price: USD {normalized['amount']} "
                        f"per {normalized['reference_unit']}, using seller-declared contents. "
                        "This comparison figure does not replace the checkout selling-unit price."
                    ),
                )
        elif fact.title == "Deterministic public unit-price comparisons":
            for pair in data["pairs"]:
                if pair["compatible_price_basis"]:
                    add(
                        fact,
                        (
                            f"Listing {pair['left_listing_id']} minus listing "
                            f"{pair['right_listing_id']}: "
                            f"USD {pair['left_minus_right_unit_price']} "
                            f"per {pair['reference_unit']} using rounded display prices. "
                            "A negative difference means the left display price is lower. "
                            "This is not a quality or overall-value ranking."
                        ),
                    )
                else:
                    add(
                        fact,
                        (
                            f"Listings {pair['left_listing_id']} and {pair['right_listing_id']} "
                            "lack a compatible known unit-price basis; no difference is inferred."
                        ),
                    )
        elif fact.title == "Current supplier comparison of selected saved quote evidence":
            add(
                fact,
                (
                    f"Rechecked on {data['as_of_date']} against input rule revision "
                    f"{data['rule_revision']}: {len(data['eligible'])} quotes eligible for cost "
                    f"comparison; {data['excluded_count']} excluded. "
                    "This is not a substitution authorization or independent quality verification."
                ),
            )
    return result
