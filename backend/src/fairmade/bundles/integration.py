"""Current bundle evidence in both saved assistant workflows."""

from sqlalchemy.orm import Session

from fairmade.assistants.schemas import Evidence, Paragraph
from fairmade.auth import api_error
from fairmade.bundles.schemas import BundleRequest
from fairmade.bundles.service import suggest
from fairmade.personalization.constants import TITLE as PROFILE_TITLE
from fairmade.personalization.service import buyer_profile_data

TITLE = "Current same-storefront product pair suggestions"


def evidence(
    db: Session, account_id: str, body: BundleRequest, *, product_id: str | None = None
) -> list[Evidence]:
    seller = product_id is not None
    snapshot = suggest(db, account_id, body, seller=seller)
    # A seller's selected owned product anchors this feature to their existing scope.
    if seller:
        from fairmade.models import MarketplaceListing

        selected = [db.get(MarketplaceListing, str(item.listing_id)) for item in body.candidates]
        if not any(row is not None and row.product_id == product_id for row in selected):
            raise api_error(409, "BUNDLE_SCOPE_MISMATCH", "Include the selected product's listing.")
    result = [
        Evidence(
            key="e1",
            title=TITLE,
            basis="seller_private_verified_sandbox_patterns_and_public_inputs"
            if seller
            else "approved_public_inputs_and_consented_buyer_affinity",
            data={
                "report": snapshot.result.model_dump(mode="json"),
                "source_fingerprint": snapshot.fingerprint,
            },
        )
    ]
    if not seller:
        selected = [listing for pair in snapshot.result.suggestions for listing in pair.listings]
        profile = buyer_profile_data(db, account_id, selected)
        if profile is not None:
            result.append(
                Evidence(
                    key="e2",
                    title=PROFILE_TITLE,
                    basis="buyer_confirmed_preferences_and_private_activity",
                    data=profile,
                )
            )
    return result


def product_context(listing: dict) -> dict:
    public = listing["payload"]["product"]
    passport = listing["passport"]["payload"]
    return {
        "title": public["title"],
        "product_type": public["product_type"],
        "quality_requirements": passport.get("quality_requirements"),
        "quality_summary": passport.get("quality_summary"),
    }


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    report = fact.data["report"]
    return {
        "role": report["role"],
        "candidates": report["candidates"],
        "suggestions": [
            {
                "products": [product_context(listing) for listing in pair["listings"]],
                "reasons": pair["reasons"],
            }
            for pair in report["suggestions"]
        ],
        "policy": report["notices"]
        + [
            "Explain only suggested eligible pairs; "
            "never invent complements, discounts or savings.",
            "No suggestions means no qualifying pair under the supplied scope; "
            "other market options remain unknown.",
        ],
    }


def statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    report = fact.data["report"]
    texts = []
    if report["budget"] is not None:
        texts.append(f"Explicit total merchandise budget: USD {report['budget']['amount']}.")
    if not report["suggestions"]:
        texts.append("No eligible pair fits the supplied candidates and current constraints.")
    for pair in report["suggestions"]:
        names = " and ".join(row["payload"]["product"]["title"] for row in pair["listings"])
        texts.append(
            f"One listed selling unit each of {names}: USD {pair['subtotal']['amount']} "
            "merchandise subtotal, equal to existing published prices without a discount."
        )
        if pair["observed_copurchase_orders"] is not None:
            texts.append(
                "Recorded verified sandbox co-purchase orders: "
                f"{pair['observed_copurchase_orders']} "
                f"from {report['history_start_date']} to exclusive {report['history_end_date']}. "
                "No refund-request orders included; this is not a demand or profit forecast."
            )
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
