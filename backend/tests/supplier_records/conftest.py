import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from fairmade.auth import hash_token
from fairmade.database import utcnow
from fairmade.models import Account, AccountRole, LoginSession

BASE = "/api/v1/seller/suppliers"


@pytest.fixture
def record_actor_factory(market_client):
    def create(roles=("buyer", "seller")):
        token = "synthetic-supplier-record-session-" + str(uuid4())
        with Session(market_client.app.state.engine) as db, db.begin():
            account = Account(
                email=str(uuid4()) + "@example.com",
                password_hash="synthetic-unused-hash",
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
def record_headers(record_actor_factory):
    return record_actor_factory()


@pytest.fixture
def profile_body():
    return {
        "request_id": str(uuid4()),
        "name": "PRIVATE_SUPPLIER",
        "location": "Private area",
        "notes": "PRIVATE_BUSINESS_NOTES",
    }


@pytest.fixture
def supplier_profile(market_client, record_headers, profile_body):
    response = market_client.post(BASE, headers=record_headers, json=profile_body)
    assert response.status_code == 201, response.text
    return response.json()["after"]


@pytest.fixture
def experience_body():
    return {
        "request_id": str(uuid4()),
        "expected_supplier_revision": 1,
        "label": "Synthetic flour delivery",
        "observed_on": "2025-05-08",
        "rating": 4,
        "promised_on": "2025-05-07",
        "received_on": "2025-05-06",
        "notes": "PRIVATE_EXPERIENCE_NOTES",
    }


@pytest.fixture
def owned_quote_factory(market_client, record_headers):
    def create(headers=None):
        headers = headers or record_headers
        product = market_client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "name": "Synthetic product",
                "product_type": "sourdough",
                "selling_unit": "loaf",
            },
        ).json()
        product_path = "/api/v1/products/" + product["id"]
        sourcing = market_client.post(
            product_path + "/sourcing-inputs", headers=headers, json={"label": "Synthetic flour"}
        ).json()
        path = product_path + "/sourcing-inputs/" + sourcing["id"]
        body = json.loads(
            (Path(__file__).parents[2] / "examples/suppliers/flour-quote.json").read_text()
        )
        response = market_client.post(path + "/supplier-quotes", headers=headers, json=body)
        assert response.status_code == 201, response.text
        return path, response.json()

    return create
