"""Synthetic sourcing evidence and server-issued sessions in migrated databases."""

import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fairmade.auth import hash_token
from fairmade.database import utcnow
from fairmade.main import create_app
from fairmade.models import Account, AccountRole, LoginSession

BACKEND = Path(__file__).parents[2]
AS_OF = date(2026, 1, 31)


@pytest.fixture(autouse=True)
def supplier_clock(monkeypatch):
    monkeypatch.setattr("fairmade.suppliers.schemas.today", lambda: AS_OF)
    monkeypatch.setattr("fairmade.suppliers.workflows.today", lambda: AS_OF)


@pytest.fixture
def quote_body():
    return json.loads((BACKEND / "examples/suppliers/flour-quote.json").read_text())


@pytest.fixture
def rules_body():
    return {
        "expected_revision": 0,
        "rules": [
            {"key": "organic", "label": "Organic claim", "type": "boolean", "expected": True}
        ],
    }


@pytest.fixture
def supplier_url(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "suppliers.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    return url


@pytest.fixture
def supplier_client(supplier_url):
    with TestClient(create_app(supplier_url)) as client:
        yield client


@pytest.fixture
def account_factory(supplier_client):
    def create(roles=("buyer", "seller")):
        token = "synthetic-session-" + str(uuid4())
        # Direct grants and sessions exist only inside test databases.
        with Session(supplier_client.app.state.engine) as db, db.begin():
            account = Account(
                email=str(uuid4()) + "@example.com",
                password_hash="synthetic-unused-test-hash",
                role_grants=[AccountRole(role=role) for role in roles],
            )
            db.add(account)
            db.flush()
            db.add(
                LoginSession(
                    token_hash=hash_token(token),
                    account_id=account.id,
                    expires_at=utcnow() + timedelta(hours=24),
                )
            )
        return {"Authorization": "Bearer " + token}

    return create


@pytest.fixture
def supplier_headers(account_factory):
    return account_factory()


@pytest.fixture
def product_path(supplier_client, supplier_headers):
    response = supplier_client.post(
        "/api/v1/products",
        headers=supplier_headers,
        json={"name": "Synthetic loaf", "product_type": "sourdough", "selling_unit": "loaf"},
    )
    assert response.status_code == 201
    return "/api/v1/products/" + response.json()["id"]


@pytest.fixture
def input_path(supplier_client, supplier_headers, product_path):
    response = supplier_client.post(
        product_path + "/sourcing-inputs",
        headers=supplier_headers,
        json={"label": "Bread flour"},
    )
    assert response.status_code == 201
    return product_path + "/sourcing-inputs/" + response.json()["id"]


@pytest.fixture
def configured_input(supplier_client, supplier_headers, input_path, rules_body):
    response = supplier_client.put(
        input_path + "/quality-locks",
        headers=supplier_headers,
        json=rules_body,
    )
    assert response.status_code == 200
    assert response.json()["rule_revision"] == 1
    return input_path
