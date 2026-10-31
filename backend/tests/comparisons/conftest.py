"""Synthetic price evidence in isolated, migrated databases."""

import json
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AccountRole

BACKEND = Path(__file__).parents[2]
AS_OF = date(2026, 1, 31)


@pytest.fixture(autouse=True)
def comparison_clock(monkeypatch):
    monkeypatch.setattr("fairmade.comparisons.schemas.today", lambda: AS_OF)
    monkeypatch.setattr("fairmade.comparisons.routes.today", lambda: AS_OF)


@pytest.fixture
def observation_body():
    body = json.loads((BACKEND / "examples/comparisons/bread-observation.json").read_text())
    body["observed_on"] = AS_OF.isoformat()
    return body


@pytest.fixture
def comparison_url(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "comparisons.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    return url


@pytest.fixture
def comparison_client(comparison_url):
    with TestClient(create_app(comparison_url)) as client:
        yield client


@pytest.fixture
def account_factory(comparison_client):
    def create(email="comparisons@example.com", roles=()):
        body = {"email": email, "password": "synthetic-comparison-password"}
        response = comparison_client.post("/api/v1/auth/register", json=body)
        assert response.status_code == 201
        with Session(comparison_client.app.state.engine) as db, db.begin():
            db.add_all(
                [
                    AccountRole(
                        account_id=response.json()["id"],
                        role=role,
                    )
                    for role in roles
                ]
            )
        login = comparison_client.post("/api/v1/auth/login", json=body)
        assert login.status_code == 200
        return {"Authorization": "Bearer " + login.json()["access_token"]}

    return create


@pytest.fixture
def comparison_headers(account_factory):
    return account_factory(roles=("seller",))


@pytest.fixture
def product_path(comparison_client, comparison_headers):
    response = comparison_client.post(
        "/api/v1/products",
        headers=comparison_headers,
        json={
            "name": "Synthetic loaf",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    )
    assert response.status_code == 201
    return "/api/v1/products/" + response.json()["id"]
