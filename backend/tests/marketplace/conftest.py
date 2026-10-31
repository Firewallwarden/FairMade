"""Synthetic sellers, private sources and explicitly approved Passports."""

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
def market_url(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "marketplace.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    return url


@pytest.fixture
def market_client(market_url):
    with TestClient(create_app(market_url)) as client:
        yield client


@pytest.fixture
def market_account(market_client):
    def create(email="private-market-seller@example.com", roles=("seller",)):
        credentials = {"email": email, "password": "synthetic-market-password"}
        created = market_client.post("/api/v1/auth/register", json=credentials)
        assert created.status_code == 201
        with Session(market_client.app.state.engine) as db, db.begin():
            db.add_all([AccountRole(account_id=created.json()["id"], role=role) for role in roles])
        token = market_client.post("/api/v1/auth/login", json=credentials).json()["access_token"]
        return {"Authorization": "Bearer " + token}

    return create


@pytest.fixture
def market_headers(market_account):
    return market_account()


@pytest.fixture
def market_source(market_client, market_headers, payload):
    def create(*, title="Public loaf", price="17.00", product_type="sourdough", headers=None):
        headers = headers or market_headers
        product = market_client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "name": "PRIVATE_MARKET_PRODUCT",
                "description": "PRIVATE_MARKET_DESCRIPTION",
                "product_type": product_type,
                "selling_unit": "loaf" if product_type == "sourdough" else "item",
            },
        ).json()
        path = "/api/v1/products/" + product["id"]
        payload["costs"][0]["label"] = "PRIVATE_MARKET_RECIPE"
        payload["labor"][0]["label"] = "PRIVATE_MARKET_WORKER"
        analysis = market_client.post(path + "/analyses", headers=headers, json=payload).json()
        review = market_client.post(
            path + "/pricing-reviews",
            headers=headers,
            json={"pricing_analysis_id": analysis["id"], "quality_evaluation_ids": []},
        )
        assert review.status_code == 201, review.text
        content = {"review_id": review.json()["id"], "title": title, "price": price}
        draft = market_client.post(path + "/passports", headers=headers, json=content)
        assert draft.status_code == 201
        draft_url = path + "/passports/" + draft.json()["id"]
        preview = market_client.get(draft_url + "/preview", headers=headers).json()
        publication = market_client.post(
            draft_url + "/publish",
            headers=headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        )
        assert publication.status_code == 201
        return {
            "path": path,
            "product": product,
            "analysis": analysis,
            "review": review.json(),
            "draft_url": draft_url,
            "passport_content": content,
            "publication": publication.json(),
        }

    return create


@pytest.fixture
def market_record(market_source):
    return market_source()


@pytest.fixture
def listing_content(market_record):
    return {
        "passport_publication_id": market_record["publication"]["id"],
        "seller_display_name": "Example bakery",
        "location": "Exampletown",
        "summary": "Synthetic listing for local testing.",
    }


@pytest.fixture
def listing(market_client, market_headers, market_record, listing_content):
    response = market_client.post(
        market_record["path"] + "/listing", headers=market_headers, json=listing_content
    )
    assert response.status_code == 201, response.text
    return response.json()
