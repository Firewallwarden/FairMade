from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from fairmade.models import AccountRole, LoginSession, ReceiptDraft, ReceiptExpense

PATH = "/api/v1/seller/receipt-drafts"


def create(client, headers, body):
    return client.post(PATH, headers=headers, json=body)


def approve(client, headers, draft):
    return client.post(
        PATH + "/" + draft["id"] + "/approve",
        headers=headers,
        json={
            "expected_revision": draft["revision"],
            "preview_hash": draft["preview_hash"],
            "approved": True,
        },
    )


def test_extract_review_approve_exactly_once(
    market_client, market_headers, receipt_body, receipt_providers
):
    gateway, reader = receipt_providers
    response = create(market_client, market_headers, receipt_body)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["state"] == "draft" and draft["approval_blockers"] == []
    assert "image_base64" not in draft and "account_id" not in draft
    assert response.headers["Cache-Control"] == "no-store"
    assert reader.calls == len(gateway.calls) == 1
    assert "Flour" in draft["ocr_text"]
    assert (
        market_client.get("/api/v1/seller/expenses", headers=market_headers).json()["items"] == []
    )
    changed = market_client.put(
        PATH + "/" + draft["id"],
        headers=market_headers,
        json={"expected_revision": 1, "details": {**draft["details"], "category": "materials"}},
    )
    assert changed.status_code == 200
    current = changed.json()
    assert current["revision"] == 2 and current["extracted"] == draft["extracted"]
    assert approve(market_client, market_headers, draft).status_code == 409
    approved = approve(market_client, market_headers, current)
    assert approved.status_code == 200
    assert approved.json()["details"]["total"] == "10.80"
    again = approve(market_client, market_headers, current)
    assert again.status_code == 200 and again.json() == approved.json()
    assert (
        len(market_client.get("/api/v1/seller/expenses", headers=market_headers).json()["items"])
        == 1
    )
    assert market_client.delete(PATH + "/" + draft["id"], headers=market_headers).status_code == 409
    assert (
        market_client.put(
            PATH + "/" + draft["id"],
            headers=market_headers,
            json={"expected_revision": 2, "details": current["details"]},
        ).status_code
        == 409
    )


def test_retries_duplicates_discard_and_pagination(
    market_client, market_headers, receipt_body, receipt_providers
):
    first = create(market_client, market_headers, receipt_body)
    assert first.status_code == 201
    retry = create(market_client, market_headers, receipt_body)
    assert retry.json() == first.json()
    assert receipt_providers[1].calls == 1
    duplicate = create(market_client, market_headers, {**receipt_body, "request_id": str(uuid4())})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "RECEIPT_ALREADY_IMPORTED"
    page = market_client.get(PATH + "?limit=1", headers=market_headers).json()
    assert len(page["items"]) == 1
    assert market_client.get(PATH + "?limit=0", headers=market_headers).status_code == 422
    assert market_client.get(PATH + "?offset=1", headers=market_headers).json()["items"] == []
    identifier = first.json()["id"]
    assert market_client.delete(PATH + "/" + identifier, headers=market_headers).status_code == 204
    assert market_client.get(PATH + "/" + identifier, headers=market_headers).status_code == 404
    assert create(market_client, market_headers, receipt_body).status_code == 201


def test_private_owner_role_and_offline_review(
    market_client, market_headers, market_account, receipt_body, receipt_providers, monkeypatch
):
    draft = create(market_client, market_headers, receipt_body).json()
    outsider = market_account(email="receipt-outsider@example.com")
    buyer = market_account(email="receipt-buyer@example.com", roles=())
    path = PATH + "/" + draft["id"]
    for headers, status in (({}, 401), (outsider, 404), (buyer, 403)):
        result = market_client.get(path, headers=headers)
        assert result.status_code == status
        assert result.headers["Cache-Control"] == "no-store"
    assert approve(market_client, outsider, draft).status_code == 404
    assert market_client.get("/api/v1/seller/expenses", headers=outsider).json()["items"] == []
    monkeypatch.setenv("FAIRMADE_RECEIPTS_ENABLED", "false")
    del market_client.app.state.assistant_gateway
    assert market_client.get(path, headers=market_headers).status_code == 200
    assert approve(market_client, market_headers, draft).status_code == 200


@pytest.mark.parametrize(
    "mutation", ["merchant", "amount", "currency", "ocr_tax", "description", "malformed"]
)
def test_unsupported_extraction_saves_nothing(
    market_client, market_headers, receipt_body, receipt_providers, mutation
):
    gateway, _ = receipt_providers
    if mutation == "merchant":
        gateway.output["merchant"] = "Invented merchant"
    elif mutation == "amount":
        gateway.output["total"] = "999.99"
    elif mutation == "currency":
        receipt_providers[1].text = receipt_providers[1].text.replace("USD", "$")
    elif mutation == "ocr_tax":
        receipt_providers[1].text = receipt_providers[1].text.replace("TAX 0.80", "TAX @.80")
    elif mutation == "description":
        gateway.output["items"][0]["description"] = "Organic certified flour"
    else:
        gateway.output = {"tool": "change inventory"}
    assert create(market_client, market_headers, receipt_body).status_code == 502
    assert market_client.get(PATH, headers=market_headers).json()["items"] == []
    assert (
        market_client.get("/api/v1/seller/expenses", headers=market_headers).json()["items"] == []
    )


def test_ambiguous_fields_and_total_mismatch_require_review(
    market_client, market_headers, receipt_body, receipt_providers
):
    gateway, _ = receipt_providers
    gateway.output["date_text"] = None
    gateway.output["currency"] = None
    draft = create(market_client, market_headers, receipt_body).json()
    assert "MISSING_PURCHASED_ON" in draft["approval_blockers"]
    assert approve(market_client, market_headers, draft).status_code == 409
    details = {
        **draft["details"],
        "purchased_on": "2026-11-10",
        "currency": "USD",
        "total": "11.00",
    }
    edited = market_client.put(
        PATH + "/" + draft["id"],
        headers=market_headers,
        json={"expected_revision": 1, "details": details},
    ).json()
    assert "TOTAL_MISMATCH" in edited["approval_blockers"]
    assert approve(market_client, market_headers, edited).status_code == 409


@pytest.mark.parametrize("revoke", ["role", "session"])
def test_revocation_during_extraction_does_not_save(
    market_client, market_headers, receipt_body, receipt_providers, revoke
):
    def callback():
        with Session(market_client.app.state.engine) as db, db.begin():
            if revoke == "role":
                db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
            else:
                db.execute(delete(LoginSession))

    receipt_providers[0].after = callback
    result = create(market_client, market_headers, receipt_body)
    assert result.status_code == (403 if revoke == "role" else 401)
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ReceiptDraft)) == 0


def test_approval_rollback_keeps_draft_and_expense_atomic(
    market_client, market_headers, receipt_body, receipt_providers, monkeypatch
):
    draft = create(market_client, market_headers, receipt_body).json()
    original = Session.add

    def fail(db, record, **kwargs):
        if isinstance(record, ReceiptExpense):
            raise RuntimeError("synthetic expense failure")
        return original(db, record, **kwargs)

    monkeypatch.setattr(Session, "add", fail)
    with pytest.raises(RuntimeError, match="synthetic expense failure"):
        approve(market_client, market_headers, draft)
    with Session(market_client.app.state.engine) as db:
        assert db.get(ReceiptDraft, draft["id"]).state == "draft"
        assert db.scalar(select(func.count()).select_from(ReceiptExpense)) == 0


def test_invalid_image_validation_redaction_and_false_approval(
    market_client, market_headers, receipt_body, receipt_providers
):
    assert (
        create(
            market_client, market_headers, {**receipt_body, "image_base64": "PRIVATE_INVALID_IMAGE"}
        ).status_code
        == 422
    )
    receipt_providers[1].text += "\nVISA 4111111111111111\nprivate@example.com"
    draft = create(market_client, market_headers, receipt_body).json()
    assert "4111111111111111" not in draft["ocr_text"]
    assert "private@example.com" not in str(receipt_providers[0].calls)
    result = market_client.post(
        PATH + "/" + draft["id"] + "/approve",
        headers=market_headers,
        json={"expected_revision": True, "preview_hash": "PRIVATE_INVALID_HASH", "approved": False},
    )
    assert result.status_code == 422
    assert "PRIVATE_INVALID_HASH" not in result.text


def test_shared_inference_slot_busy(market_client, market_headers, receipt_body, receipt_providers):
    from fairmade.assistants.runtime import INFERENCE_SLOT

    assert INFERENCE_SLOT.acquire(blocking=False)
    try:
        assert create(market_client, market_headers, receipt_body).status_code == 429
    finally:
        INFERENCE_SLOT.release()
    assert receipt_providers[1].calls == 0


def test_parallel_approval_records_one_expense(
    market_client, market_headers, receipt_body, receipt_providers
):
    from concurrent.futures import ThreadPoolExecutor

    draft = create(market_client, market_headers, receipt_body).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: approve(market_client, market_headers, draft), range(2))
        )
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ReceiptExpense)) == 1
