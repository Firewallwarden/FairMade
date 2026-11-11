from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

BACKEND = Path(__file__).parents[2]


def test_new_table_matches_metadata_and_empty_rollback_preserves_products(
    market_client,
    market_headers,
    market_record,
):
    config = Config(str(BACKEND / "alembic.ini"))
    before = market_client.get(market_record["path"], headers=market_headers).json()
    command.check(config)
    command.downgrade(config, "0024")
    assert "description_drafts" not in inspect(market_client.app.state.engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get(market_record["path"], headers=market_headers).json() == before


def test_drafts_block_downgrade_and_database_enforces_review_state(
    market_client,
    market_headers,
    description_path,
    description_gateway,
):
    from uuid import uuid4

    created = market_client.post(
        description_path, headers=market_headers, json={"request_id": str(uuid4())}
    )
    assert created.status_code == 201
    config = Config(str(BACKEND / "alembic.ini"))
    for assignment in ("revision=0", "state='approved'", "description=''", "provider='cloud'"):
        with pytest.raises(IntegrityError), market_client.app.state.engine.begin() as connection:
            connection.execute(text("UPDATE description_drafts SET " + assignment))
    with pytest.raises(RuntimeError, match="description draft review history"):
        command.downgrade(config, "0024")
    command.check(config)
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
