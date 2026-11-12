import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import ReceiptDraft, ReceiptExpense


class InsightGateway:
    def __init__(self):
        self.calls = []
        self.after = None

    def complete(self, messages, schema):
        self.calls.append(messages)
        if "proposed_prices" in schema["properties"]:
            return {"proposed_prices": []}
        if self.after:
            self.after()
        facts = json.loads(messages[-1]["content"])["EVIDENCE"]
        return {
            "paragraphs": [
                {
                    "text": "Review the recorded evidence and preserve mandatory quality.",
                    "evidence_keys": [facts[-1]["key"]],
                }
            ]
        }


@pytest.fixture
def insight_gateway(market_client):
    gateway = InsightGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def insight_listing(market_client, market_headers, market_source):
    def create(price="0.01"):
        source = market_source(price=price)
        path = source["path"] + "/listing"
        draft = market_client.post(
            path,
            headers=market_headers,
            json={
                "passport_publication_id": source["publication"]["id"],
                "selling_quantity": {"value": "1", "unit": "item"},
                "seller_display_name": "Example bakery",
            },
        )
        assert draft.status_code == 201
        preview = market_client.get(path + "/preview", headers=market_headers).json()
        approved = market_client.post(
            path + "/activate",
            headers=market_headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        )
        assert approved.status_code == 200
        return {**source, "listing": approved.json()}

    return create


@pytest.fixture
def receipt_evidence(market_client, market_headers):
    owner = market_client.get("/api/v1/auth/me", headers=market_headers).json()["id"]

    def seed(amount, days_ago=2, approved=True, account_id=None):
        account = account_id or owner
        details = {
            "merchant": "PRIVATE_RECEIPT_MERCHANT",
            "purchased_on": (utcnow().date() - timedelta(days=days_ago)).isoformat(),
            "currency": "USD",
            "subtotal": amount,
            "tax": "0.00",
            "total": amount,
            "category": "materials",
            "items": [{"description": "PRIVATE_RECEIPT_ITEM", "line_total": amount}],
        }
        with Session(market_client.app.state.engine) as db, db.begin():
            row = ReceiptDraft(
                account_id=account,
                request_id=str(uuid4()),
                source_hash=uuid4().hex + uuid4().hex,
                revision=1,
                state="approved" if approved else "draft",
                ocr_text="PRIVATE_RECEIPT_OCR",
                provenance={"basis": "synthetic_test"},
                extracted={},
                details=details,
                approved_at=utcnow() if approved else None,
            )
            db.add(row)
            db.flush()
            if approved:
                db.add(ReceiptExpense(receipt_id=row.id, account_id=account, details=details))
        return details

    return seed


@pytest.fixture
def production_evidence(market_client, market_headers):
    def create(source, total=10, sellable=7, correction=None):
        body = {
            "request_id": str(uuid4()),
            "label": "PRIVATE_PRODUCTION_LABEL",
            "kind": "batch",
            "started_on": (utcnow().date() - timedelta(days=3)).isoformat(),
            "completed_on": (utcnow().date() - timedelta(days=2)).isoformat(),
            "selling_unit": "loaf",
            "total_units": total,
            "sellable_units": sellable,
            "currency": "USD",
            "costs": [],
            "labor": [],
        }
        if correction:
            body.update(corrects_record_id=correction, correction_reason="Synthetic correction")
        response = market_client.post(
            source["path"] + "/production-records", headers=market_headers, json=body
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create
