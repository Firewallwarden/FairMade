"""Owner-only receipt evidence; reusable aggregate arithmetic lives with receipts."""

from sqlalchemy.orm import Session

from fairmade.assistants.schemas import Evidence, HistoryPeriod, Paragraph
from fairmade.receipts.aggregates import LIMITATIONS, reviewed_totals

TITLE = "Private seller-wide reviewed receipt expenses"


def expense_evidence(
    db: Session, account_id: str, period: HistoryPeriod, facts: list[Evidence]
) -> None:
    totals = reviewed_totals(db, account_id, period.start_date, period.end_date)
    facts.append(
        Evidence(
            key=f"e{len(facts) + 1}",
            title=TITLE,
            basis="seller_reviewed_unverified",
            data=totals.model_dump(mode="json"),
        )
    )


def expense_context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    return {
        "scope": "Seller-wide approved receipt records, not selected-product costs.",
        "status": (
            "Approved receipt expenses exist in this period."
            if fact.data["receipt_count"]
            else "No approved receipt expenses recorded in this period; actual spending is unknown."
        ),
        "recorded_categories": list(fact.data["category_totals"]),
        "limitations": LIMITATIONS,
    }


def expense_statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    data = fact.data
    texts = [
        f"Seller-wide reviewed receipt records from {data['start_date']} to "
        f"{data['end_date']} (exclusive): {data['receipt_count']} receipts; "
        f"recorded total USD {data['recorded_total']}. Not total actual business spending.",
    ]
    texts.extend(
        f"Seller-assigned receipt category {category}: USD {amount}."
        for category, amount in data["category_totals"].items()
    )
    texts.append(
        "Receipt totals are separate evidence; they are not deducted again from modeled profit."
    )
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
