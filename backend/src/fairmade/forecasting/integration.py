"""Qualitative model context and exact server facts for saved seller conversations."""

from fairmade.assistants.schemas import Evidence, Paragraph

TITLE = "Private product observed sales baseline and inventory projection"


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    data = fact.data
    inventory = data["inventory"]
    return {
        "status": data["status"],
        "environment": data["environment"],
        "basis": data["basis"],
        "inventory_status": inventory["status"],
        "additional_units_indicated": inventory["additional_whole_units"] is not None
        and inventory["additional_whole_units"] > 0,
        "warnings": data["warnings"],
        "policy": data["notices"]
        + [
            "Historical units and conditional projection outcomes appear in calculated facts.",
            "Explain assumptions; do not invent demand, confidence or change production/stock.",
            "A sparse sample is insufficient, not evidence of zero demand or guaranteed forecasts.",
            "Lookback and horizon are fixed by the reviewed scope; "
            "a changed request needs a new reviewed scope, not an automatic chat action.",
        ],
    }


def statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    data = fact.data
    history = data["history"]
    unit = data["selling_unit"]
    texts = [
        f"Observed sandbox sales for this product: {history['units']} {unit} selling units "
        f"over {history['complete_days']} complete UTC dates from {history['start_date']} "
        f"through exclusive {history['end_date']}; "
        f"qualifying sales on {history['sale_dates']} dates."
    ]
    if data["status"] == "insufficient_history":
        texts.append(
            "Insufficient recorded history for a sales-rate baseline; no forecast is given."
        )
    else:
        texts.append(
            f"Conditional observed sales rate: {data['daily_rate']} {unit} selling units per day. "
            f"At that rate, the next {data['request']['horizon_days']} days project "
            f"{data['projected_units']} selling units. This is not a demand guarantee."
        )
    inventory = data["inventory"]
    if inventory["status"] == "known":
        texts.append(
            f"Current seller-recorded available stock: {inventory['available_units']} "
            f"{unit} selling units."
        )
        if inventory["additional_whole_units"] is not None:
            texts.append(
                f"Conditional projected remaining stock: {inventory['projected_remaining_units']} "
                f"selling units; additional whole selling units to cover this baseline: "
                f"{inventory['additional_whole_units']}. Conditional stock coverage: "
                f"{inventory['days_of_cover']} days. No stock or production change is authorized."
            )
    else:
        texts.append(
            "Inventory basis is unknown; no stock-coverage or additional-unit estimate is given."
        )
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
