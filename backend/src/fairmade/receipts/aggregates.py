"""Owner-scoped reviewed receipt totals shared by reporting and assistant explanations."""

from datetime import date
from decimal import Decimal, localcontext
from typing import Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.models import ReceiptDraft, ReceiptExpense
from fairmade.pricing.schemas import Contract
from fairmade.receipts.schemas import ExpenseDetails


class ExpenseTotals(Contract):
    start_date: date
    end_date: date
    currency: Literal["USD"] = "USD"
    receipt_count: int
    recorded_total: Decimal
    category_totals: dict[str, Decimal]
    limitations: list[str]


LIMITATIONS = [
    "Only approved seller-reviewed receipt records; not a complete expense or bank ledger.",
    "Purchase dates and categories are seller-confirmed and unverified.",
    "Each receipt total has one seller-selected category; not item-level cost allocation.",
    "Do not subtract these totals from modeled profit: production costs may already include them.",
    "No attribution to the selected product, stock consumption or payment verification.",
]


def reviewed_totals(
    db: Session, account_id: str, start_date: date, end_date: date
) -> ExpenseTotals:
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
                purchase_date >= start_date.isoformat(),
                purchase_date < end_date.isoformat(),
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

    return ExpenseTotals(
        start_date=start_date,
        end_date=end_date,
        currency="USD",
        receipt_count=len(records),
        recorded_total=Decimal(format(total, ".2f")),
        category_totals={
            key: Decimal(format(value, ".2f")) for key, value in sorted(categories.items())
        },
        limitations=LIMITATIONS,
    )
