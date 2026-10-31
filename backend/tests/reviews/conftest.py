"""Synthetic saved evidence for private seller pricing review tests."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fairmade.comparisons.schemas import ComparisonRequest, ObservationSnapshot
from fairmade.comparisons.service import compare
from fairmade.main import create_app
from fairmade.models import AccountRole
from fairmade.pricing.schemas import PricingRequest
from fairmade.pricing.service import calculate

BACKEND = Path(__file__).parents[2]
REVIEW_DATE = date(2026, 1, 31)


@pytest.fixture
def evidence(payload):
    product = {
        "id": str(uuid4()),
        "name": "Synthetic loaf",
        "product_type": "sourdough",
        "selling_unit": "loaf",
        "description": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    rule = {"key": "flag", "label": "Synthetic mandatory flag", "type": "boolean", "expected": True}
    observation = ObservationSnapshot.model_validate(
        {
            "id": str(uuid4()),
            "details": {
                "label": "Synthetic quote",
                "product_type": "sourdough",
                "currency": "USD",
                "price": "8",
                "quantity": {"value": "500", "unit": "g"},
                "source": {"name": "Fictional", "kind": "document", "reference": "Synthetic"},
                "location": "Fictional",
                "observed_on": REVIEW_DATE.isoformat(),
            },
        }
    )
    request = ComparisonRequest.model_validate(
        {
            "observation_ids": [str(observation.id)],
            "target_quantity": {"value": "100", "unit": "g"},
        }
    )
    return {
        "product": product,
        "pricing_analysis": {
            "id": str(uuid4()),
            "product_snapshot": dict(product),
            "inputs": payload,
            "result": calculate(PricingRequest.model_validate(payload)).model_dump(mode="json"),
        },
        "quality_lock_set": {"revision": 1, "rules": [rule]},
        "quality_evaluations": [
            {
                "id": str(uuid4()),
                "candidate_label": "Synthetic candidate",
                "rule_revision": 1,
                "rules_snapshot": [rule],
                "status": "passed",
                "checks": [{"key": "flag", "status": "passed", "reason_code": "MATCHED"}],
            }
        ],
        "comparison_report": {
            "id": str(uuid4()),
            "product_snapshot": dict(product),
            "request_snapshot": request.model_dump(mode="json"),
            "as_of_date": REVIEW_DATE.isoformat(),
            "result": compare(request, [observation], "sourdough", REVIEW_DATE).model_dump(
                mode="json"
            ),
        },
    }


@pytest.fixture
def review_url(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "reviews.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    monkeypatch.setattr("fairmade.reviews.routes.utcnow", lambda: datetime(2026, 1, 31, tzinfo=UTC))
    monkeypatch.setattr("fairmade.comparisons.schemas.today", lambda: REVIEW_DATE)
    monkeypatch.setattr("fairmade.comparisons.routes.today", lambda: REVIEW_DATE)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    return url


@pytest.fixture
def review_client(review_url):
    with TestClient(create_app(review_url)) as client:
        yield client


@pytest.fixture
def account_factory(review_client):
    def create(email="reviews@example.com", roles=()):
        body = {"email": email, "password": "synthetic-review-password"}
        response = review_client.post("/api/v1/auth/register", json=body)
        assert response.status_code == 201
        with Session(review_client.app.state.engine) as db, db.begin():
            db.add_all([AccountRole(account_id=response.json()["id"], role=role) for role in roles])
        token = review_client.post("/api/v1/auth/login", json=body).json()["access_token"]
        return {"Authorization": "Bearer " + token}

    return create


@pytest.fixture
def review_headers(account_factory):
    return account_factory(roles=("seller",))


@pytest.fixture
def selected_evidence(review_client, review_headers, payload):
    product = review_client.post(
        "/api/v1/products",
        headers=review_headers,
        json={
            "name": "Synthetic loaf",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    ).json()
    path = "/api/v1/products/" + product["id"]
    analysis = review_client.post(path + "/analyses", headers=review_headers, json=payload)
    assert analysis.status_code == 201
    rule_body = {
        "expected_revision": 0,
        "rules": [
            {
                "key": "flag",
                "label": "Synthetic required flag",
                "type": "boolean",
                "expected": True,
            },
        ],
    }
    assert (
        review_client.put(
            path + "/quality-locks", headers=review_headers, json=rule_body
        ).status_code
        == 200
    )
    quality = review_client.post(
        path + "/quality-evaluations",
        headers=review_headers,
        json={
            "candidate_label": "Synthetic candidate",
            "expected_revision": 1,
            "claims": {"flag": {"type": "boolean", "value": True}},
        },
    )
    assert quality.status_code == 201
    observation_body = json.loads(
        (BACKEND / "examples/comparisons/bread-observation.json").read_text()
    )
    observation_body["observed_on"] = REVIEW_DATE.isoformat()
    observation = review_client.post(
        path + "/price-observations", headers=review_headers, json=observation_body
    )
    assert observation.status_code == 201
    comparison = review_client.post(
        path + "/price-comparisons",
        headers=review_headers,
        json={
            "observation_ids": [observation.json()["id"]],
            "target_quantity": {"value": "100", "unit": "g"},
        },
    )
    assert comparison.status_code == 201
    return {
        "path": path,
        "analysis": analysis.json(),
        "quality": quality.json(),
        "comparison": comparison.json(),
        "request": {
            "pricing_analysis_id": analysis.json()["id"],
            "comparison_report_id": comparison.json()["id"],
            "quality_evaluation_ids": [quality.json()["id"]],
            "production_unit_quantity": {"value": "500", "unit": "g"},
        },
    }
