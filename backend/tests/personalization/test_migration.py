from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

BACKEND = Path(__file__).parents[2]


def test_metadata_empty_rollback_and_account_preservation(market_client, buyer_headers):
    config = Config(str(BACKEND / "alembic.ini"))
    before = market_client.get("/api/v1/auth/me", headers=buyer_headers).json()
    command.check(config)
    command.downgrade(config, "0027")
    assert "buyer_profiles" not in inspect(market_client.app.state.engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get("/api/v1/auth/me", headers=buyer_headers).json() == before


def test_stateful_profile_blocks_lossy_rollback(market_client, enabled_profile):
    config = Config(str(BACKEND / "alembic.ini"))
    with pytest.raises(RuntimeError, match="buyer profile revision history"):
        command.downgrade(config, "0027")
    command.check(config)
