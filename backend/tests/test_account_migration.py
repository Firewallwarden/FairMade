"""Exercise upgrades from the released seller-only schema with real linked data."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, select, text
from sqlalchemy.orm import Session

from fairmade.auth import hash_token, hasher
from fairmade.database import make_engine
from fairmade.main import create_app
from fairmade.models import AccountRole
from fairmade.pricing.schemas import PricingRequest
from fairmade.pricing.service import calculate


def test_populated_0001_upgrade_preserves_data_and_defaults_to_buyer(
    tmp_path, monkeypatch, payload
):
    url = "sqlite:///" + (tmp_path / "legacy.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", url)
    monkeypatch.delenv("FAIRMADE_CORS_ORIGINS", raising=False)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "0001")
    engine = make_engine(url)
    account_id, other_id, product_id, analysis_id = [str(uuid4()) for _ in range(4)]
    now = datetime.now(UTC)
    # Synthetic test credentials, never an actual account or session.
    test_password = "migration-test-password"
    test_token = "synthetic-migration-session"
    password_hash = hasher.hash(test_password)
    snapshot = {
        "id": product_id,
        "name": "Legacy demo loaf",
        "product_type": "sourdough",
        "selling_unit": "loaf",
        "description": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    calculated = calculate(PricingRequest.model_validate(payload)).model_dump(mode="json")
    metadata = MetaData()
    metadata.reflect(engine)
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["sellers"].insert(),
            [
                {
                    "id": account_id,
                    "email": "legacy@example.com",
                    "password_hash": password_hash,
                    "created_at": now,
                },
                {
                    "id": other_id,
                    "email": "empty@example.com",
                    "password_hash": password_hash,
                    "created_at": now,
                },
            ],
        )
        connection.execute(
            metadata.tables["sessions"].insert(),
            {
                "token_hash": hash_token(test_token),
                "seller_id": account_id,
                "created_at": now,
                "expires_at": now + timedelta(hours=24),
            },
        )
        connection.execute(
            metadata.tables["products"].insert(),
            {
                "id": product_id,
                "seller_id": account_id,
                "name": snapshot["name"],
                "product_type": "sourdough",
                "selling_unit": "loaf",
                "description": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            metadata.tables["analyses"].insert(),
            {
                "id": analysis_id,
                "product_id": product_id,
                "created_at": now,
                "calculation_version": calculated["calculation_version"],
                "product_snapshot": snapshot,
                "inputs": payload,
                "result": calculated,
            },
        )
        before = {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
            for table in ("sellers", "sessions", "products", "analyses")
        }
    engine.dispose()

    command.upgrade(config, "head")
    command.check(config)
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
            for old_table, new_table in (
                ("sellers", "accounts"),
                ("sessions", "sessions"),
                ("products", "products"),
                ("analyses", "analyses"),
            ):
                assert (
                    connection.execute(text(f"SELECT * FROM {new_table} ORDER BY 1")).all()
                    == before[old_table]
                )
            grants = connection.execute(text("SELECT account_id, role FROM account_roles")).all()
            assert set(grants) == {(account_id, "buyer"), (other_id, "buyer")}
        headers = {"Authorization": f"Bearer {test_token}"}
        path = f"/api/v1/products/{product_id}"
        with TestClient(create_app(url)) as client:
            me = client.get("/api/v1/auth/me", headers=headers)
            assert me.status_code == 200
            assert me.json() == {
                "id": account_id,
                "email": "legacy@example.com",
                "roles": ["buyer"],
            }
            login = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "legacy@example.com",
                    "password": test_password,
                },
            )
            assert login.status_code == 200
            assert client.get(path, headers=headers).status_code == 403
            assert (
                client.post("/api/v1/seller-applications", headers=headers, json={}).status_code
                == 201
            )
            assert client.get(path, headers=headers).status_code == 403
            # A test-only grant simulates future successful verification.
            with Session(engine) as db, db.begin():
                db.add(AccountRole(account_id=account_id, role="seller"))
            saved = client.get(path + "/analyses/" + analysis_id, headers=headers)
            assert saved.status_code == 200
            assert saved.json()["inputs"] == payload
            assert saved.json()["result"] == calculated
            assert saved.json()["product_snapshot"]["name"] == snapshot["name"]
            assert saved.json()["id"] == analysis_id
            assert client.patch(path, headers=headers, json={"name": "New name"}).status_code == 200

        # Return product state to its original snapshot before testing downgrade.
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE products SET name = :name, updated_at = :updated_at WHERE id = :id"),
                {
                    "name": snapshot["name"],
                    "updated_at": before["products"][0][-1],
                    "id": product_id,
                },
            )
            # Remove the new login so exact legacy session comparisons remain meaningful.
            connection.execute(
                text("DELETE FROM sessions WHERE token_hash != :token"),
                {"token": hash_token(test_token)},
            )
        command.downgrade(config, "0001")
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
            for table in ("sellers", "sessions", "products", "analyses"):
                assert (
                    connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
                    == before[table]
                )
        command.upgrade(config, "head")
        command.check(config)
        with Session(engine) as db:
            assert {
                (grant.account_id, grant.role) for grant in db.scalars(select(AccountRole))
            } == {(account_id, "buyer"), (other_id, "buyer")}
    finally:
        engine.dispose()
