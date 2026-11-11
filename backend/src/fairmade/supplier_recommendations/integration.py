"""Qualitative model context and server-calculated supplier review facts."""

from fairmade.assistants.schemas import Evidence, Paragraph

TITLE = "Current supplier recommendation mode and optional preference tradeoffs"


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    data = fact.data
    return {
        "mode": data["options"]["mode"],
        "cost_objective": data["options"]["cost_objective"],
        "preferences_in_priority_order": data["options"]["preferences"],
        "candidates": [
            {
                "supplier_name": row["supplier_name"],
                "eligible": row["eligible"],
                "mandatory_checks": row["mandatory_checks"],
                "optional_preference_checks": row["preference_checks"],
                "exclusions": row["exclusion_reasons"],
                "selected_for_input_review": row["selected_for_input_review"],
            }
            for row in data["rows"]
        ],
        "product_impact": data["product_impact"],
        "notices": data["notices"],
    }


def statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    data = fact.data
    texts = [
        f"Supplier review mode: {data['options']['mode']}; "
        f"cost objective: {data['options']['cost_objective']}. "
        f"Current sourcing rule revision {data['rule_revision']} as of {data['as_of_date']}.",
        "Selection is for sourcing-input review only; finished-product impact is unassessed "
        "and no substitution or saving is authorized.",
    ]
    for row in data["rows"]:
        name = row["supplier_name"]
        if not row["eligible"]:
            texts.append(f"{name}: EXCLUDED; not an acceptable saving or substitution.")
        else:
            cost = row["cost"]
            status = (
                "Selected for input review" if row["selected_for_input_review"] else "Not selected"
            )
            texts.append(
                f"{name}: {status}; purchase outlay USD {cost['purchase_cost']}, "
                f"cost per usable {data['required_quantity']['unit']} "
                f"USD {cost['cost_per_usable_unit']}. Supplied claims remain unverified."
            )
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
