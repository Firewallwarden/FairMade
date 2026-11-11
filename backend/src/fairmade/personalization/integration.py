"""Buyer-only personalization evidence and exact facts for the existing assistant."""

from fairmade.assistants.schemas import Evidence, Paragraph
from fairmade.personalization.constants import TITLE


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    preferences = fact.data["preferences"]
    return {
        "budget_limit_recorded": preferences["budget_per_item"] is not None,
        "selected_product_types": preferences["product_types"],
        "location_filter_recorded": preferences["location"] is not None,
        "matches": fact.data["matches"],
        "policy": fact.data["policy"]
        + [
            "Never recommend a listing marked eligible false or relax explicit buyer constraints.",
            "Calculated facts show budget and eligibility. Activity is not a quality finding.",
        ],
    }


def statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    budget = fact.data["preferences"]["budget_per_item"]
    texts = [
        f"Your confirmed per-listed-unit budget is USD {budget}; unmodeled fees are excluded."
        if budget is not None
        else "No confirmed per-listed-unit budget is recorded.",
    ]
    for match in fact.data["matches"]:
        texts.append(
            f"Selected listing {match['listing_id']}: "
            + (
                "matches current shopping filters."
                if match["eligible"]
                else "excluded by current shopping filters: " + ", ".join(match["exclusions"]) + "."
            )
        )
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
