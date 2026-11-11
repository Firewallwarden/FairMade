"""Explain conditional advice; numerical ranges remain deterministic server facts."""

from fairmade.assistants.schemas import Evidence, Paragraph

TITLE = "Current conditional sustainable price recommendation"


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    data = fact.data
    return {
        "status": data["status"],
        "quality_status": data["quality_status"],
        "market_status": data["market_status"],
        "recommendation_available": data["recommended_review_range"] is not None,
        "reasons": data["reasons"],
        "notices": data["notices"],
    }


def statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    data = fact.data
    unit = data["analysis_selling_unit"]
    texts = [
        f"Conditional pricing review status: {data['status']}. "
        f"Analysis saved on {data['analysis_saved_on']}; reassessed as of {data['as_of_date']}.",
        f"Historical modeled basis per {unit}: unit cost USD {data['unit_cost']}, "
        f"fee-aware break-even USD {data['break_even_price']}; "
        f"seller target range USD {data['seller_target_range']['minimum']} "
        f"to USD {data['seller_target_range']['maximum']}.",
    ]
    market = data["selected_market_range"]
    if market is not None:
        reference = data["market_reference_quantity"]
        texts.append(
            "Selected descriptive market context for the seller-declared production unit "
            f"({reference['value']} {reference['unit']}): "
            f"USD {market['minimum']} "
            f"to USD {market['maximum']}. Quality equivalence and locality are not verified."
        )
    selected = data["recommended_review_range"]
    if selected is None:
        texts.append(
            "No price recommendation is available under these quality, basis or range gaps."
        )
    else:
        texts.append(
            f"Conditional range for seller review per {unit}: USD {selected['minimum']} "
            f"to USD {selected['maximum']}. No price was selected or published."
        )
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
