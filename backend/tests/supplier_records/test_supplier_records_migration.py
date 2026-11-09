"""New profile audit preservation and safe migration across earlier livestock history."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from fairmade.main import create_app

BASE = "/api/v1/seller/suppliers"
BACKEND = Path(__file__).parents[2]
TABLES = {"supplier_profiles", "supplier_profile_events", "supplier_experiences"}


def test_supplier_history_blocks_downgrade_and_survives_restart(
    market_client,
    record_headers,
    supplier_profile,
    experience_body,
    market_url,
):
    path = BASE + "/" + supplier_profile["id"]
    original = market_client.post(
        path + "/experiences", headers=record_headers, json=experience_body
    ).json()
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    for target in ("0023", "base"):
        with pytest.raises(RuntimeError, match="supplier experience"):
            command.downgrade(config, target)
        command.check(config)
        assert TABLES.issubset(inspect(market_client.app.state.engine).get_table_names())
    with TestClient(create_app(market_url)) as restarted:
        assert (
            restarted.get(path + "/experiences/" + original["id"], headers=record_headers).json()
            == original
        )
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_empty_supplier_migration_preserves_existing_livestock_and_quote(
    market_client,
    record_headers,
    owned_quote_factory,
):
    group = market_client.post(
        "/api/v1/seller/livestock/groups",
        headers=record_headers,
        json={
            "request_id": str(uuid4()),
            "occurred_on": "2025-05-01",
            "reason": "Synthetic group",
            "name": "Existing flock",
            "species": "chicken",
        },
    ).json()["after"]
    group_path = "/api/v1/seller/livestock/groups/" + group["id"]
    before = market_client.get(group_path, headers=record_headers).json()
    quote_path, quote = owned_quote_factory()
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0023")
    assert not TABLES.intersection(inspect(market_client.app.state.engine).get_table_names())
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get(group_path, headers=record_headers).json() == before
    assert (
        market_client.get(
            quote_path + "/supplier-quotes/" + quote["id"], headers=record_headers
        ).json()
        == quote
    )
    assert market_client.get(BASE, headers=record_headers).json()["items"] == []
    # Wider rollback must refuse before dropping the empty supplier tables, too.
    with pytest.raises(RuntimeError, match="livestock"):
        command.downgrade(config, "base")
    command.check(config)


def test_database_constraints_protect_reported_rating_and_dates(
    market_client,
    record_headers,
    supplier_profile,
    experience_body,
):
    path = BASE + "/" + supplier_profile["id"]
    assert (
        market_client.post(
            path + "/experiences", headers=record_headers, json=experience_body
        ).status_code
        == 201
    )
    engine = market_client.app.state.engine
    for assignment in ("rating=0", "rating=6", "supplier_revision=0", "received_on='2999-01-01'"):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text("UPDATE supplier_experiences SET " + assignment))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE supplier_profiles SET archived=2"))
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
