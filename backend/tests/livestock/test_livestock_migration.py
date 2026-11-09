"""Preserve prior production data and preflight protected history before SQLite DDL."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from fairmade.main import create_app

from .test_livestock_api import BASE

BACKEND = Path(__file__).parents[2]
TABLES = {
    "livestock_groups",
    "livestock_animals",
    "livestock_group_events",
    "livestock_animal_events",
    "production_livestock_sources",
}


def test_prior_completed_records_survive_upgrade_and_empty_roundtrip(
    market_client,
    market_headers,
    livestock_product,
    livestock_production_body,
):
    path = livestock_product + "/production-records"
    original = market_client.post(
        path, headers=market_headers, json=livestock_production_body
    ).json()
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0022")
    assert not TABLES.intersection(inspect(market_client.app.state.engine).get_table_names())
    # Simulate the previous release's request JSON while schema 0022 is active.
    with market_client.app.state.engine.begin() as connection:
        request = connection.execute(text("SELECT request FROM production_records")).scalar_one()
        legacy = json.loads(request)
        legacy.pop("livestock_source", None)
        connection.execute(
            text("UPDATE production_records SET request=:request"), {"request": json.dumps(legacy)}
        )
    command.upgrade(config, "head")
    command.check(config)
    detail = market_client.get(path + "/" + original["id"], headers=market_headers).json()
    assert detail["result"] == original["result"]
    assert detail["livestock_snapshot"] is None
    assert "livestock_source" not in detail["request"]
    assert (
        market_client.post(path, headers=market_headers, json=livestock_production_body).status_code
        == 200
    )
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_new_livestock_history_blocks_downgrade_without_partial_ddl(
    market_client,
    market_headers,
    livestock_group,
    livestock_animal,
    market_url,
):
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    for target in ("0022", "base"):
        with pytest.raises(RuntimeError, match="livestock"):
            command.downgrade(config, target)
        command.check(config)
        assert TABLES.issubset(inspect(market_client.app.state.engine).get_table_names())
    with TestClient(create_app(market_url)) as restarted:
        group = restarted.get(
            BASE + "/groups/" + livestock_group["id"], headers=market_headers
        ).json()
        assert group["registered_active_animals"] == 1
        assert (
            restarted.get(
                BASE + "/animals/" + livestock_animal["id"], headers=market_headers
            ).json()
            == livestock_animal
        )


def test_database_constraints_and_foreign_keys(
    market_client,
    market_headers,
    livestock_group,
):
    from sqlalchemy.exc import IntegrityError

    engine = market_client.app.state.engine
    for assignment in (
        "reported_headcount=-1",
        "reported_headcount=NULL",
        "headcount_on=NULL",
        "archived=2",
        "revision=0",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text("UPDATE livestock_groups SET " + assignment))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO production_livestock_sources "
                "(record_id,group_id,animal_id,snapshot) VALUES (:id,:group,NULL,'{}')"
            ),
            {"id": str(uuid4()), "group": livestock_group["id"]},
        )
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
