"""Private canary evidence used to test exact, explicit public disclosure."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AccountRole

BACKEND = Path(__file__).parents[2]


@pytest.fixture
def passport_url(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "passports.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    return url


@pytest.fixture
def passport_client(passport_url):
    with TestClient(create_app(passport_url)) as client:
        yield client


@pytest.fixture
def account_factory(passport_client):
    def create(email="private-seller@example.com", roles=()):
        credentials = {"email": email, "password": "synthetic-passport-password"}
        created = passport_client.post("/api/v1/auth/register", json=credentials)
        assert created.status_code == 201
        with Session(passport_client.app.state.engine) as db, db.begin():
            db.add_all([AccountRole(account_id=created.json()["id"], role=role) for role in roles])
        token = passport_client.post("/api/v1/auth/login", json=credentials).json()["access_token"]
        return {"Authorization": "Bearer " + token}

    return create


@pytest.fixture
def seller_headers(account_factory):
    return account_factory(roles=("seller",))


@pytest.fixture
def source(passport_client, seller_headers, payload):
    client, headers = passport_client, seller_headers
    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "PRIVATE_PRODUCT_NAME",
            "description": "PRIVATE_PRODUCT_DESCRIPTION",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    ).json()
    path = "/api/v1/products/" + product["id"]
    payload["costs"][0]["label"] = "PRIVATE_INGREDIENT_NAME"
    payload["labor"][0]["label"] = "PRIVATE_WORKER_NAME"
    analysis = client.post(path + "/analyses", headers=headers, json=payload)
    assert analysis.status_code == 201
    assert (
        client.put(
            path + "/quality-locks",
            headers=headers,
            json={
                "expected_revision": 0,
                "rules": [
                    {
                        "key": "welfare",
                        "label": "PRIVATE_REQUIREMENT_LABEL",
                        "type": "boolean",
                        "expected": True,
                    }
                ],
            },
        ).status_code
        == 200
    )
    quality = client.post(
        path + "/quality-evaluations",
        headers=headers,
        json={
            "candidate_label": "PRIVATE_SUPPLIER_NAME",
            "expected_revision": 1,
            "claims": {"welfare": {"type": "boolean", "value": False}},
        },
    )
    assert quality.status_code == 201
    observed = client.post(
        path + "/price-observations",
        headers=headers,
        json={
            "label": "PRIVATE_QUOTE_LABEL",
            "product_type": "sourdough",
            "currency": "USD",
            "price": "8",
            "quantity": {"value": "500", "unit": "g"},
            "source": {
                "name": "PRIVATE_QUOTE_SOURCE",
                "kind": "document",
                "reference": "PRIVATE_RECEIPT",
            },
            "location": "PRIVATE_LOCATION",
            "observed_on": datetime.now(UTC).date().isoformat(),
            "quality_notes": "PRIVATE_QUOTE_NOTES",
        },
    )
    assert observed.status_code == 201
    comparison = client.post(
        path + "/price-comparisons",
        headers=headers,
        json={
            "observation_ids": [observed.json()["id"]],
            "target_quantity": {"value": "100", "unit": "g"},
        },
    )
    assert comparison.status_code == 201
    review = client.post(
        path + "/pricing-reviews",
        headers=headers,
        json={
            "pricing_analysis_id": analysis.json()["id"],
            "quality_evaluation_ids": [quality.json()["id"]],
            "comparison_report_id": comparison.json()["id"],
            "production_unit_quantity": {"value": "500", "unit": "g"},
        },
    )
    assert review.status_code == 201
    return {
        "path": path,
        "product": product,
        "review": review.json(),
        "analysis_id": analysis.json()["id"],
        "quality_id": quality.json()["id"],
        "observation_id": observed.json()["id"],
        "comparison_id": comparison.json()["id"],
    }


@pytest.fixture
def content(source):
    return {
        "review_id": source["review"]["id"],
        "title": "Seller-approved public loaf",
        "price": "17.00",
    }


@pytest.fixture
def draft(passport_client, seller_headers, source, content):
    response = passport_client.post(
        source["path"] + "/passports", headers=seller_headers, json=content
    )
    assert response.status_code == 201, response.text
    return response.json()
