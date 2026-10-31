"""Isolated quality fixtures with synthetic seller grants and example claims."""

import json
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
def lock_body():
    return json.loads((BACKEND / "examples/quality/sourdough-locks.json").read_text())


@pytest.fixture
def candidate_body():
    return json.loads((BACKEND / "examples/quality/sourdough-candidate.json").read_text())


@pytest.fixture
def quality_url(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "quality.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    return url


@pytest.fixture
def quality_client(quality_url):
    with TestClient(create_app(quality_url)) as client:
        yield client


@pytest.fixture
def account_factory(quality_client):
    def create(email="quality@example.com", roles=()):
        # Synthetic credentials and direct grants exist only in tests.
        body = {"email": email, "password": "quality-test-password"}
        registration = quality_client.post("/api/v1/auth/register", json=body)
        assert registration.status_code == 201
        with Session(quality_client.app.state.engine) as db, db.begin():
            db.add_all(
                [
                    AccountRole(
                        account_id=registration.json()["id"],
                        role=role,
                    )
                    for role in roles
                ]
            )
        login = quality_client.post("/api/v1/auth/login", json=body)
        assert login.status_code == 200
        return {"Authorization": "Bearer " + login.json()["access_token"]}

    return create


@pytest.fixture
def quality_headers(account_factory):
    return account_factory(roles=("seller",))


@pytest.fixture
def product_path(quality_client, quality_headers):
    response = quality_client.post(
        "/api/v1/products",
        headers=quality_headers,
        json={
            "name": "Synthetic loaf",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    )
    assert response.status_code == 201
    return "/api/v1/products/" + response.json()["id"]
