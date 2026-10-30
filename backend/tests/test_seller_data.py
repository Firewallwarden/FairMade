"""Integration tests use migrated, isolated on-disk SQLite databases."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fairmade import auth
from fairmade.auth import hash_token, hasher
from fairmade.database import make_engine
from fairmade.main import create_app
from fairmade.models import Analysis, LoginSession, Product, Seller

ROOT = Path(__file__).parents[1]
PASSWORD = "  development-password  "
PRODUCT = {"name": "Test sourdough", "product_type": "sourdough", "selling_unit": "loaf"}


@pytest.fixture
def migrated_url(tmp_path, monkeypatch):
    url = "sqlite:///" + (tmp_path / "seller.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    return url


@pytest.fixture
def seller_client(migrated_url):
    with TestClient(create_app(migrated_url)) as client:
        yield client


def login(client, email="seller@example.com", password=PASSWORD):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


def account(client, email="seller@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    token = login(client, email)["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers(seller_client):
    return account(seller_client)


def product(client, headers, **overrides):
    response = client.post("/api/v1/products", headers=headers, json={**PRODUCT, **overrides})
    assert response.status_code == 201
    return response.json()


def test_account_password_and_session_storage(seller_client, headers):
    me = seller_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert set(me.json()) == {"id", "email"}
    with Session(seller_client.app.state.engine) as db:
        seller = db.scalar(select(Seller))
        session = db.scalar(select(LoginSession))
        assert seller.password_hash.startswith("$argon2id$")
        assert PASSWORD not in seller.password_hash
        assert hasher.verify(seller.password_hash, PASSWORD)
        token = headers["Authorization"].split()[1]
        assert session.token_hash == hash_token(token)
        assert session.token_hash != token
        assert session.expires_at - session.created_at == timedelta(hours=24)
    # Password whitespace is significant.
    response = seller_client.post(
        "/api/v1/auth/login",
        json={"email": "seller@example.com", "password": PASSWORD.strip()},
    )
    missing = seller_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": PASSWORD},
    )
    assert response.status_code == missing.status_code == 401
    assert response.json() == missing.json()
    assert response.headers["www-authenticate"] == "Bearer"


def test_email_normalization_and_conflict(seller_client):
    body = {"email": " Seller@EXAMPLE.com ", "password": PASSWORD}
    response = seller_client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    assert response.json()["email"] == "seller@example.com"
    body["email"] = "SELLER@example.com"
    response = seller_client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EMAIL_EXISTS"
    assert login(seller_client, "SELLER@example.com")["token_type"] == "bearer"


@pytest.mark.parametrize("route", ["register", "login"])
@pytest.mark.parametrize(
    "body",
    [
        {"email": "seller@example.com", "password": "shortsecret"},
        {"email": "bad", "password": PASSWORD},
        {"email": "seller@example.com", "password": "s" * 129},
        {"email": "seller@example.com", "password": PASSWORD, "unexpected": PASSWORD},
        [PASSWORD],
    ],
)
def test_credential_validation_does_not_echo_secrets(seller_client, route, body):
    response = seller_client.post(f"/api/v1/auth/{route}", json=body)
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert "shortsecret" not in response.text
    assert "s" * 129 not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])


def test_session_expiry_is_fixed_and_exact(seller_client, monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(auth, "utcnow", lambda: start)
    headers = account(seller_client)
    monkeypatch.setattr(auth, "utcnow", lambda: start + timedelta(hours=23))
    assert seller_client.get("/api/v1/auth/me", headers=headers).status_code == 200
    monkeypatch.setattr(
        auth,
        "utcnow",
        lambda: start + timedelta(hours=24, microseconds=-1),
    )
    assert seller_client.get("/api/v1/auth/me", headers=headers).status_code == 200
    monkeypatch.setattr(auth, "utcnow", lambda: start + timedelta(hours=24))
    assert seller_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    with Session(seller_client.app.state.engine) as db:
        assert db.scalar(select(LoginSession)).expires_at == (start + timedelta(hours=24)).replace(
            tzinfo=None,
        )


def test_logout_revokes_only_current_session(seller_client, headers):
    second = {"Authorization": "Bearer " + login(seller_client)["access_token"]}
    assert second != headers
    assert seller_client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert seller_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert seller_client.post("/api/v1/auth/logout", headers=headers).status_code == 401
    assert seller_client.get("/api/v1/auth/me", headers=second).status_code == 200


@pytest.mark.parametrize("authorization", [None, "Bearer unknown", "Basic abc", "Bearer"])
def test_missing_or_invalid_authentication(seller_client, authorization, payload):
    headers = {"Authorization": authorization} if authorization else {}
    pid, aid = uuid4(), uuid4()
    routes = [
        ("get", "/api/v1/auth/me", None),
        ("post", "/api/v1/auth/logout", None),
        ("get", "/api/v1/products", None),
        ("post", "/api/v1/products", PRODUCT),
        ("get", f"/api/v1/products/{pid}", None),
        ("patch", f"/api/v1/products/{pid}", {"name": "Updated"}),
        ("get", f"/api/v1/products/{pid}/analyses", None),
        ("post", f"/api/v1/products/{pid}/analyses", payload),
        ("get", f"/api/v1/products/{pid}/analyses/{aid}", None),
    ]
    for method, path, body in routes:
        response = seller_client.request(method, path, headers=headers, json=body)
        assert response.status_code == 401, (method, path, response.text)


def test_products_and_snapshot_history(seller_client, headers, payload):
    item = product(seller_client, headers, description="Seller-reported test data")
    path = f"/api/v1/products/{item['id']}"
    assert item["created_at"].endswith("Z")
    assert seller_client.get(path, headers=headers).json() == item
    response = seller_client.post(path + "/analyses", headers=headers, json=payload)
    assert response.status_code == 201
    saved = response.json()
    expected = seller_client.post("/api/v1/pricing/analyze", json=payload).json()
    assert saved["result"] == expected
    assert saved["inputs"] == payload
    assert saved["product_snapshot"] == item
    assert saved["result"]["costs"]["unit_cost"] == "10.000000"
    updated = seller_client.patch(
        path,
        headers=headers,
        json={"name": "Renamed", "description": None},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["description"] is None
    assert updated.json()["updated_at"] >= item["updated_at"]
    detail = path + "/analyses/" + saved["id"]
    assert seller_client.get(detail, headers=headers).json() == saved
    history = seller_client.get(path + "/analyses", headers=headers).json()
    assert history == {
        "items": [
            {
                "id": saved["id"],
                "created_at": saved["created_at"],
                "calculation_version": "production-economics-v1",
            }
        ],
        "limit": 20,
        "offset": 0,
    }
    for method in ("patch", "delete"):
        assert seller_client.request(method, detail, headers=headers).status_code == 405


def test_ownership_on_every_product_and_history_route(seller_client, headers, payload):
    item = product(seller_client, headers)
    path = f"/api/v1/products/{item['id']}"
    saved = seller_client.post(path + "/analyses", headers=headers, json=payload).json()
    other = account(seller_client, "other@example.com")
    assert seller_client.get("/api/v1/products", headers=other).json()["items"] == []
    for prefix in (path, f"/api/v1/products/{uuid4()}"):
        for method, suffix, body in [
            ("get", "", None),
            ("patch", "", {"name": "Stolen"}),
            ("post", "/analyses", payload),
            ("get", "/analyses", None),
            ("get", "/analyses/" + saved["id"], None),
        ]:
            response = seller_client.request(method, prefix + suffix, headers=other, json=body)
            assert response.status_code == 404
            assert response.json()["detail"]["code"] == "NOT_FOUND"
    other_item = product(seller_client, headers, name="Another owned product")
    wrong = f"/api/v1/products/{other_item['id']}/analyses/{saved['id']}"
    assert seller_client.get(wrong, headers=headers).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"name": " "},
        {"name": "x" * 201},
        {"product_type": "unknown"},
        {"selling_unit": ""},
        {"description": "x" * 2001},
        {"name": None},
        {"product_type": None},
        {"selling_unit": None},
        {"seller_id": str(uuid4())},
    ],
)
def test_product_validation(seller_client, headers, body):
    item = product(seller_client, headers)
    response = seller_client.patch(
        f"/api/v1/products/{item['id']}",
        headers=headers,
        json=body,
    )
    assert response.status_code == 422
    assert (
        seller_client.post(
            "/api/v1/products",
            headers=headers,
            json={**PRODUCT, **body},
        ).status_code
        == 422
    )


def test_pagination_and_stable_ties(seller_client, headers, payload):
    first = product(seller_client, headers)
    second = product(seller_client, headers, product_type="eggs", selling_unit="dozen eggs")
    with Session(seller_client.app.state.engine) as db, db.begin():
        for item in db.scalars(select(Product)):
            item.created_at = datetime(2026, 1, 1)
    expected = sorted([first["id"], second["id"]], reverse=True)
    for offset, expected_id in enumerate(expected):
        page = seller_client.get(
            f"/api/v1/products?limit=1&offset={offset}",
            headers=headers,
        ).json()
        assert page["limit"] == 1 and page["offset"] == offset
        assert [item["id"] for item in page["items"]] == [expected_id]
    path = f"/api/v1/products/{first['id']}/analyses"
    ids = [seller_client.post(path, headers=headers, json=payload).json()["id"] for _ in range(2)]
    with Session(seller_client.app.state.engine) as db, db.begin():
        for item in db.scalars(select(Analysis)):
            item.created_at = datetime(2026, 1, 1)
    assert seller_client.get(path + "?limit=1&offset=1", headers=headers).json()["items"][0][
        "id"
    ] == min(ids)
    for suffix in ("?limit=0", "?limit=101", "?offset=-1"):
        for url in ("/api/v1/products", path):
            assert seller_client.get(url + suffix, headers=headers).status_code == 422


def test_bad_pricing_inputs_do_not_create_history(seller_client, headers, payload):
    item = product(seller_client, headers)
    path = f"/api/v1/products/{item['id']}/analyses"
    payload["sellable_units"] = 0
    assert seller_client.post(path, headers=headers, json=payload).status_code == 422
    assert seller_client.get(path, headers=headers).json()["items"] == []


@pytest.mark.parametrize("failure_event", ["after_flush", "before_commit"])
def test_failed_analysis_transaction_rolls_back(
    seller_client,
    headers,
    payload,
    migrated_url,
    failure_event,
):
    item = product(seller_client, headers)
    path = f"/api/v1/products/{item['id']}/analyses"

    def fail_write(db, *_args):
        if any(isinstance(obj, Analysis) for obj in db.new):
            raise RuntimeError("Simulated storage failure")

    event.listen(Session, failure_event, fail_write)
    try:
        with TestClient(create_app(migrated_url), raise_server_exceptions=False) as failing:
            response = failing.post(path, headers=headers, json=payload)
            assert response.status_code == 500
    finally:
        event.remove(Session, failure_event, fail_write)
    assert seller_client.get(path, headers=headers).json()["items"] == []
    assert seller_client.post(path, headers=headers, json=payload).status_code == 201


def test_migrations_foreign_keys_and_restart(migrated_url, payload):
    config = Config(str(ROOT / "alembic.ini"))
    command.check(config)
    with TestClient(create_app(migrated_url)) as client:
        headers = account(client)
        item = product(client, headers)
        path = f"/api/v1/products/{item['id']}/analyses"
        saved = client.post(path, headers=headers, json=payload).json()
        with Session(client.app.state.engine) as db:
            assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
            db.add(Product(seller_id=str(uuid4()), **PRODUCT))
            with pytest.raises(IntegrityError):
                db.flush()
    with TestClient(create_app(migrated_url)) as restarted:
        assert restarted.get(path + "/" + saved["id"], headers=headers).json() == saved
    command.downgrade(config, "base")
    engine = make_engine(migrated_url)
    try:
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()
    command.upgrade(config, "head")


def test_openapi_errors_and_bearer_scheme(seller_client):
    schema = seller_client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    operation = schema["paths"]["/api/v1/products"]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert "401" in operation["responses"] and "422" in operation["responses"]
    password = schema["components"]["schemas"]["Credentials"]["properties"]["password"]
    assert password["writeOnly"] is True
    assert password["minLength"] == 12
    patch_name = schema["components"]["schemas"]["ProductUpdate"]["properties"]["name"]
    assert patch_name["type"] == "string"


@pytest.mark.parametrize("field", ["name", "product_type", "selling_unit"])
def test_product_creation_requires_fields(seller_client, headers, field):
    body = dict(PRODUCT)
    del body[field]
    assert (
        seller_client.post(
            "/api/v1/products",
            headers=headers,
            json=body,
        ).status_code
        == 422
    )


def test_history_preserves_decimal_precision_and_defaults(seller_client, headers, payload):
    item = product(seller_client, headers)
    path = f"/api/v1/products/{item['id']}/analyses"
    payload["costs"] = [{"label": "Synthetic input", "category": "materials", "amount": "1.000001"}]
    payload["labor"] = []
    payload["sellable_units"] = 3
    del payload["proposed_prices"]
    response = seller_client.post(path, headers=headers, json=payload)
    assert response.status_code == 201
    saved = response.json()
    assert saved["inputs"]["costs"][0]["amount"] == "1.000001"
    assert saved["inputs"]["proposed_prices"] == []
    assert saved["result"]["costs"]["unit_cost"] == "0.333334"
    assert seller_client.get(path + "/" + saved["id"], headers=headers).json() == saved
    # Historical result reads must not depend on current calculator code.
    with Session(seller_client.app.state.engine) as db, db.begin():
        row = db.get(Analysis, saved["id"])
        row.calculation_version = "historical-test-version"
        row.result = {**row.result, "calculation_version": "historical-test-version"}
    historic = seller_client.get(path + "/" + saved["id"], headers=headers)
    assert historic.status_code == 200
    assert historic.json()["result"]["calculation_version"] == "historical-test-version"


def test_cors_requires_explicit_origins(migrated_url, monkeypatch):
    with TestClient(create_app(migrated_url)) as client:
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert "access-control-allow-origin" not in response.headers
    monkeypatch.setenv("FAIRMADE_CORS_ORIGINS", "http://localhost:5173")
    with TestClient(create_app(migrated_url)) as client:
        response = client.options(
            "/api/v1/products",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        response = client.get("/health", headers={"Origin": "http://unapproved.example"})
        assert "access-control-allow-origin" not in response.headers
    monkeypatch.setenv("FAIRMADE_CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="wildcard"):
        create_app(migrated_url)
