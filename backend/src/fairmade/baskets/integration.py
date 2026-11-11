"""Recomputed basket evidence in the existing saved buyer conversation workflow."""

from sqlalchemy.orm import Session

from fairmade.assistants.schemas import Evidence, Paragraph
from fairmade.baskets.schemas import BasketRequest
from fairmade.baskets.service import optimize
from fairmade.personalization.constants import TITLE as PROFILE_TITLE
from fairmade.personalization.service import buyer_profile_data

TITLE = "Deterministic single-storefront basket plan"


def evidence(db: Session, account_id: str, body: BasketRequest) -> list[Evidence]:
    snapshot = optimize(db, account_id, body)
    facts = [
        Evidence(
            key="e1",
            title=TITLE,
            basis="calculated_from_approved_public_inputs",
            data={
                "plan": snapshot.result.model_dump(mode="json"),
                "source_fingerprint": snapshot.fingerprint,
                "selected_quality": [
                    {
                        "listing_id": str(item.id),
                        "quality_requirements": [
                            rule.model_dump(mode="json")
                            for rule in item.passport.payload.quality_requirements or []
                        ],
                        "quality_summary": item.passport.payload.quality_summary.model_dump(
                            mode="json"
                        )
                        if item.passport.payload.quality_summary
                        else None,
                    }
                    for item in snapshot.selected
                ],
            },
        )
    ]
    profile = buyer_profile_data(db, account_id, snapshot.selected)
    if profile is not None:
        # Preserve the established erasure marker even when a plan is infeasible.
        facts.append(
            Evidence(
                key="e2",
                title=PROFILE_TITLE,
                basis="buyer_confirmed_preferences_and_private_activity",
                data=profile,
            )
        )
    return facts


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    plan = fact.data["plan"]
    return {
        "status": plan["status"],
        "needs": plan["needs"],
        "selected_products": [line["listing"]["product"] for line in plan["preview"]["items"]]
        if plan["preview"] is not None
        else [],
        "selected_quality": fact.data["selected_quality"],
        "policy": plan["notices"]
        + [
            "Calculated facts show exact selected items, quantities, prices and budget outcomes.",
            "Explain constraints and limitations; never override exclusions "
            "or recommend an unaffordable/incomplete plan.",
            "Basket scope is fixed for this conversation; request a reviewed new scope "
            "for changed quantities or alternatives.",
        ],
    }


def statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    plan = fact.data["plan"]
    texts = []
    subtotal = plan["minimum_subtotal"]
    if subtotal is not None:
        texts.append(
            "Minimum complete merchandise subtotal among your supplied eligible alternatives: "
            f"USD {subtotal['amount']}."
        )
    if plan["budget"] is not None:
        texts.append(f"Your explicit total merchandise budget: USD {plan['budget']['amount']}.")
    if plan["status"] == "over_budget":
        texts.append("No complete basket fits this budget; no purchase cart is recommended.")
    elif plan["status"] == "unavailable":
        texts.append("No complete basket meets every requested quantity and current constraint.")
    else:
        for line in plan["preview"]["items"]:
            texts.append(
                f"Selected listing {line['listing_id']}: {line['quantity']} listed selling units "
                f"at USD {line['unit_price']['amount']} each; "
                f"merchandise line subtotal USD {line['subtotal']['amount']}."
            )
        if plan["remaining_budget"] is not None:
            texts.append(f"Remaining merchandise budget: USD {plan['remaining_budget']['amount']}.")
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
