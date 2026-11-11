"""Owner-only aggregates of approved receipt expenses, never additional modeled costs."""

from decimal import Decimal, localcontext

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.assistants.schemas import Evidence, HistoryPeriod, Paragraph
from fairmade.auth import api_error
from fairmade.models import ReceiptDraft, ReceiptExpense
from fairmade.receipts.schemas import ExpenseDetails

TITLE = "Private seller-wide reviewed receipt expenses"
LIMITATIONS = [
    "Only approved seller-reviewed receipt records; not a complete expense or bank ledger.",
    "Purchase dates and categories are seller-confirmed and unverified.",
    "Each receipt total has one seller-selected category; not item-level cost allocation.",
    "Do not subtract these totals from modeled profit: production costs may already include them.",
    "No attribution to the selected product, stock consumption or payment verification.",
]


def expense_evidence(
    db: Session, account_id: str, period: HistoryPeriod, facts: list[Evidence]
) -> None:
    purchase_date = ReceiptExpense.details["purchased_on"].as_string()
    records = (
        db.execute(
            select(
                ReceiptExpense.details["total"].as_string().label("total"),
                ReceiptExpense.details["currency"].as_string().label("currency"),
                ReceiptExpense.details["category"].as_string().label("category"),
            )
            .join(ReceiptDraft, ReceiptDraft.id == ReceiptExpense.receipt_id)
            .where(
                ReceiptExpense.account_id == account_id,
                ReceiptDraft.account_id == account_id,
                ReceiptDraft.state == "approved",
                purchase_date >= period.start_date.isoformat(),
                purchase_date < period.end_date.isoformat(),
            )
            .order_by(ReceiptExpense.id)
            .limit(201)
        )
        .mappings()
        .all()
    )
    if len(records) > 200:
        raise api_error(409, "ASSISTANT_EXPENSE_REPORT_TOO_LARGE", "Narrow the expense period.")
    categories: dict[str, Decimal] = {}
    with localcontext() as context:
        context.prec = 40
        total = Decimal("0.00")
        for record in records:
            try:
                item = ExpenseDetails.model_validate(dict(record))
            except ValidationError:
                raise api_error(
                    409, "UNSUPPORTED_EXPENSE_EVIDENCE", "Expense evidence is incomplete."
                ) from None
            if item.currency != "USD" or item.total is None or item.total <= 0:
                raise api_error(
                    409, "UNSUPPORTED_EXPENSE_EVIDENCE", "Expense evidence is incomplete."
                )
            total += item.total
            categories[item.category] = categories.get(item.category, Decimal(0)) + item.total
    facts.append(
        Evidence(
            key=f"e{len(facts) + 1}",
            title=TITLE,
            basis="seller_reviewed_unverified",
            data={
                "start_date": period.start_date.isoformat(),
                "end_date": period.end_date.isoformat(),
                "currency": "USD",
                "receipt_count": len(records),
                "recorded_total": format(total, ".2f"),
                "category_totals": {
                    key: format(value, ".2f") for key, value in sorted(categories.items())
                },
                "limitations": LIMITATIONS,
            },
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
