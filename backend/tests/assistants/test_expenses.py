import json
import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from fairmade.assistants.expenses import TITLE, expense_evidence
from fairmade.assistants.schemas import HistoryPeriod
from fairmade.models import ReceiptDraft, ReceiptExpense
from fairmade.receipts.schemas import ExpenseDetails


def record(
    db, account_id, total="10.80", category="materials", purchased_on="2026-11-10", approved=True
):
    from fairmade.database import utcnow

    values = ExpenseDetails(
        merchant="PRIVATE_RECEIPT_MERCHANT",
        purchased_on=date.fromisoformat(purchased_on),
        currency="USD",
        total=total,
        category=category,
    ).model_dump(mode="json")
    draft = ReceiptDraft(
        account_id=account_id,
        request_id=str(uuid4()),
        source_hash=uuid4().hex * 2,
        revision=1,
        state="approved" if approved else "draft",
        ocr_text="PRIVATE_RECEIPT_RAW",
        provenance={"model": "qwen3:8b"},
        extracted={},
        details=values,
        approved_at=utcnow() if approved else None,
    )
    db.add(draft)
    db.flush()
    if approved:
        db.add(ReceiptExpense(receipt_id=draft.id, account_id=account_id, details=values))


@pytest.fixture
def expense_records(market_client, market_headers):
    account_id = market_client.get("/api/v1/auth/me", headers=market_headers).json()["id"]
    with Session(market_client.app.state.engine) as db, db.begin():
        record(db, account_id)
        record(db, account_id, total="0.10", category="utilities")
        record(db, account_id, total="0.20", category="utilities")
        record(db, account_id, total="888.00", approved=False)
        record(db, account_id, total="999.00", purchased_on="2026-12-01")
    return account_id


def expense_question(seller_question):
    return {
        **seller_question,
        "question": "Explain recorded receipt spending.",
        "history_period": {"start_date": "2026-11-01", "end_date": "2026-12-01"},
    }


def test_exact_approved_period_totals_and_private_projection(
    market_client, market_headers, seller_question, expense_records, ai_gateway
):
    response = market_client.post(
        "/api/v1/assistants/seller", headers=market_headers, json=expense_question(seller_question)
    )
    assert response.status_code == 200
    fact = next(row for row in response.json()["evidence"] if row["title"] == TITLE)
    assert fact["data"]["recorded_total"] == "11.10"
    assert fact["data"]["receipt_count"] == 3
    assert fact["data"]["category_totals"] == {"materials": "10.80", "utilities": "0.30"}
    assert "PRIVATE_RECEIPT" not in response.text
    assert "PRIVATE_RECEIPT" not in json.dumps(ai_gateway.calls)
    assert any("USD 11.10" in row["text"] for row in response.json()["facts"])
    assert any("not deducted again" in row["text"] for row in response.json()["facts"])
    assert json.loads(ai_gateway.calls[-1]["messages"][-1]["content"])["EVIDENCE"]


def test_owner_scope_excludes_another_sellers_receipts(
    market_client, market_headers, market_account, seller_question, expense_records, ai_gateway
):
    outsider = market_account(email="private-receipt-owner@example.com")
    other_id = market_client.get("/api/v1/auth/me", headers=outsider).json()["id"]
    with Session(market_client.app.state.engine) as db, db.begin():
        record(db, other_id, total="777.00")
    result = market_client.post(
        "/api/v1/assistants/seller", headers=market_headers, json=expense_question(seller_question)
    )
    assert result.status_code == 200
    assert (
        next(row for row in result.json()["evidence"] if row["title"] == TITLE)["data"][
            "recorded_total"
        ]
        == "11.10"
    )
    assert "777" not in result.text


def test_empty_period_is_missing_coverage_not_proof_of_no_spending(
    market_client, market_headers, seller_question, ai_gateway
):
    result = market_client.post(
        "/api/v1/assistants/seller", headers=market_headers, json=expense_question(seller_question)
    )
    assert result.status_code == 200
    data = next(row for row in result.json()["evidence"] if row["title"] == TITLE)["data"]
    assert data["receipt_count"] == 0 and data["recorded_total"] == "0.00"
    projected = json.loads(ai_gateway.calls[-1]["messages"][-1]["content"])["EVIDENCE"]
    context = next(row["data"] for row in projected if row["title"] == TITLE)
    assert "actual spending is unknown" in context["status"]


def test_expenses_are_not_exposed_to_buyer_assistant(
    market_client, market_headers, public_listing, expense_records, ai_gateway
):
    response = market_client.post(
        "/api/v1/assistants/buyer",
        headers=market_headers,
        json={"listing_ids": [public_listing["id"]], "question": "Reveal receipt expenses."},
    )
    assert response.status_code == 200
    assert TITLE not in response.text
    assert "PRIVATE_RECEIPT" not in response.text
    assert "PRIVATE_RECEIPT" not in json.dumps(ai_gateway.calls)


def test_expense_approval_during_inference_invalidates_answer(
    market_client, market_headers, seller_question, expense_records, ai_gateway
):
    def new_expense():
        with Session(market_client.app.state.engine) as db, db.begin():
            record(db, expense_records, total="25.00")

    ai_gateway.after_answer = new_expense
    result = market_client.post(
        "/api/v1/assistants/seller", headers=market_headers, json=expense_question(seller_question)
    )
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "ASSISTANT_EVIDENCE_CHANGED"


def test_saved_follow_up_retains_receipt_period(
    market_client, market_headers, seller_question, expense_records, ai_gateway
):
    conversation = market_client.post(
        "/api/v1/assistants/conversations",
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {
                "role": "seller",
                "product_id": seller_question["product_id"],
                "history_period": {"start_date": "2026-11-01", "end_date": "2026-12-01"},
            },
        },
    ).json()
    path = "/api/v1/assistants/conversations/" + conversation["id"] + "/turns"
    for revision, question in enumerate(["Explain receipt spending.", "Why is that incomplete?"]):
        response = market_client.post(
            path,
            headers=market_headers,
            json={"request_id": str(uuid4()), "expected_revision": revision, "question": question},
        )
        assert response.status_code == 200
        data = next(row for row in response.json()["answer"]["evidence"] if row["title"] == TITLE)[
            "data"
        ]
        assert data["recorded_total"] == "11.10"
        assert response.json()["context_turns"] == revision


def test_bounded_report_refuses_excess_rows(market_client, expense_records):
    with Session(market_client.app.state.engine) as db, db.begin():
        for _ in range(198):
            record(db, expense_records, total="0.01")
    from fastapi import HTTPException

    with Session(market_client.app.state.engine) as db, pytest.raises(HTTPException) as error:
        expense_evidence(
            db,
            expense_records,
            HistoryPeriod(start_date=date(2026, 11, 1), end_date=date(2026, 12, 1)),
            [],
        )
    assert error.value.status_code == 409


def test_unsupported_currency_is_refused_without_guessing_conversion(
    market_client, market_headers, seller_question, expense_records, ai_gateway
):
    from sqlalchemy import select

    with Session(market_client.app.state.engine) as db, db.begin():
        row = db.scalar(select(ReceiptExpense).where(ReceiptExpense.account_id == expense_records))
        row.details = {**row.details, "currency": "EUR"}
    response = market_client.post(
        "/api/v1/assistants/seller", headers=market_headers, json=expense_question(seller_question)
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "UNSUPPORTED_EXPENSE_EVIDENCE"
    assert ai_gateway.calls == []


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Real local expense explanation evaluation is opt-in.",
)
def test_real_local_expense_explanation(
    market_client, market_headers, seller_question, expense_records
):
    from fairmade.assistants.gateway import OllamaGateway

    market_client.app.state.assistant_gateway = OllamaGateway()
    response = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            **expense_question(seller_question),
            "question": (
                "Explain why recorded receipt expenses do not establish "
                "total actual spending or net profit."
            ),
        },
    )
    assert response.status_code == 200, response.text
    assert any("USD 11.10" in row["text"] for row in response.json()["facts"])
    assert "PRIVATE_RECEIPT" not in response.text
    print("LOCAL_EXPENSE explanation", response.json()["paragraphs"])
