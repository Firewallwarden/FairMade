from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .conftest import send

BACKEND = Path(__file__).parents[2]


def test_empty_message_migration_preserves_existing_order(
    market_client, buyer_headers, message_order
):
    config = Config(str(BACKEND / "alembic.ini"))
    path = "/api/v1/orders/" + message_order["id"]
    before = market_client.get(path, headers=buyer_headers).json()
    command.check(config)
    command.downgrade(config, "0028")
    assert "order_messages" not in inspect(market_client.app.state.engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get(path, headers=buyer_headers).json() == before


def test_message_history_blocks_lossy_downgrade(market_client, buyer_headers, message_path):
    assert send(market_client, buyer_headers, message_path).status_code == 201
    config = Config(str(BACKEND / "alembic.ini"))
    with pytest.raises(RuntimeError, match="order message history"):
        command.downgrade(config, "0028")
    command.check(config)
    assert len(market_client.get(message_path, headers=buyer_headers).json()["items"]) == 1


def test_wider_refused_downgrade_keeps_new_empty_table(market_client, buyer_headers):
    profile = market_client.put(
        "/api/v1/buyer/personalization",
        headers=buyer_headers,
        json={
            "expected_revision": 0,
            "confirmed": True,
            "enabled": True,
            "preferences": {},
        },
    )
    assert profile.status_code == 200
    config = Config(str(BACKEND / "alembic.ini"))
    with pytest.raises(RuntimeError, match="buyer profile revision history"):
        command.downgrade(config, "0027")
    assert "order_messages" in inspect(market_client.app.state.engine).get_table_names()
    command.check(config)
