"""Cautious model view and exact numerical facts for private seller insight evidence."""

from fairmade.assistants.schemas import Evidence, Paragraph

TITLE = "Private seller opportunities and on-demand alerts"


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    data = fact.data
    return {
        "pricing_status": data["pricing"]["status"],
        "cost_history_status": data["costs"]["status"],
        "receipt_baseline_available": bool(
            data["receipts"]["current"]["receipt_count"]
            and data["receipts"]["previous"]["receipt_count"]
        ),
        "alerts": data["alerts"],
        "policy": data["notices"],
    }


def statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    data = fact.data
    texts = []
    price = data["pricing"]
    if price["status"] == "assessed":
        texts.append(
            f"At the approved USD {price['price']} price per {data['selling_unit']}, "
            f"using analysis saved on {price['analysis_saved_on']}, "
            f"modeled profit per unit is USD {price['profit_per_unit']} "
            f"and margin is {price['margin']}. "
            f"Fee-aware break-even is USD {price['break_even_price']}; seller-target price range "
            f"is USD {price['target_price_minimum']} to {price['target_price_maximum']}."
        )
    else:
        texts.append("Current-price margin assessment is unavailable: " + price["status"] + ".")
    costs = data["costs"]
    if costs["status"] == "available":
        texts.append(
            f"Closed-period compatible saved unit costs: USD {costs['previous_unit_cost']} "
            f"then USD {costs['current_unit_cost']}; change USD {costs['difference']['change']}. "
            f"Snapshots saved on {costs['previous_saved_on']} and {costs['current_saved_on']}. "
            "Save-time evidence does not establish expense inflation or a cause."
        )
    receipts = data["receipts"]
    for label in ("previous", "current"):
        values = receipts[label]
        texts.append(
            f"Seller-wide {label} approved receipt records from {values['start_date']} "
            f"to exclusive {values['end_date']}: {values['receipt_count']} receipts, "
            f"USD {values['recorded_total']}. These totals are not additional product costs."
        )
    output = data["production"]
    texts.append(
        f"Effective product production records: {output['included_records']}; "
        f"total output {output['total_units']}, sellable {output['sellable_units']}, "
        f"non-sellable {output['non_sellable_units']} in {data['selling_unit']} selling units. "
        "Non-sellable output is not automatically waste or an avoidable loss."
    )
    for material in data["materials"]:
        texts.append(
            f"Seller-wide recorded material waste for {material['label']}: "
            f"{material['quantity']} {material['unit']} "
            f"across {material['movement_count']} events. "
            "No product allocation, cost valuation or avoidable-loss claim is established."
        )
    texts.extend(alert["message"] + " " + alert["suggested_review"] for alert in data["alerts"])
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
