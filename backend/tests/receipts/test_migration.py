from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

BACKEND = Path(__file__).parents[2]


def test_metadata_and_empty_rollback(market_client, market_record, market_headers):
    config = Config(str(BACKEND / "alembic.ini"))
    before = market_client.get(market_record["path"], headers=market_headers).json()
    command.check(config)
    command.downgrade(config, "0026")
    assert "receipt_drafts" not in inspect(market_client.app.state.engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get(market_record["path"], headers=market_headers).json() == before


def test_refuses_lossy_rollback(market_client, market_headers, receipt_body, receipt_providers):
    response = market_client.post(
        "/api/v1/seller/receipt-drafts", headers=market_headers, json=receipt_body
    )
    assert response.status_code == 201
    config = Config(str(BACKEND / "alembic.ini"))
    with pytest.raises(RuntimeError, match="receipt or expense history"):
        command.downgrade(config, "0026")
    command.check(config)
