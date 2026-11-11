from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

BACKEND = Path(__file__).parents[2]


def test_conversation_tables_match_metadata_and_empty_downgrade_preserves_product(
    market_client, market_record, market_headers
):
    config = Config(str(BACKEND / "alembic.ini"))
    before = market_client.get(market_record["path"], headers=market_headers).json()
    command.check(config)
    command.downgrade(config, "0025")
    tables = inspect(market_client.app.state.engine).get_table_names()
    assert "assistant_conversations" not in tables
    assert "assistant_turns" not in tables
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get(market_record["path"], headers=market_headers).json() == before


def test_conversations_block_lossy_downgrade_and_constraints_hold(
    market_client, market_headers, market_record
):
    from uuid import uuid4

    created = market_client.post(
        "/api/v1/assistants/conversations",
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {"role": "seller", "product_id": market_record["product"]["id"]},
        },
    )
    assert created.status_code == 201
    config = Config(str(BACKEND / "alembic.ini"))
    for assignment in ("revision=-1", "revision=41", "role='admin'"):
        with pytest.raises(IntegrityError), market_client.app.state.engine.begin() as connection:
            connection.execute(text("UPDATE assistant_conversations SET " + assignment))
    with pytest.raises(RuntimeError, match="assistant conversation history"):
        command.downgrade(config, "0025")
    command.check(config)
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
