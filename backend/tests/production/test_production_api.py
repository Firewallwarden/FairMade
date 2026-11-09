"""Private actual reports, immutable corrections, retries and failure recovery."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import Analysis, ProductionRecord

BACKEND = Path(__file__).parents[2]


def save(client, headers, product, body):
    return client.post(product + "/production-records", headers=headers, json=body)


def correction(body, prior, **changes):
    return {
        **body,
        "request_id": str(uuid4()),
        "corrects_record_id": prior["id"],
        "correction_reason": "Synthetic correction of reported output",
        **changes,
    }


def test_snapshot_retry_and_product_unit_changes(
    market_client, market_headers, production_product, production_body
):
    before = market_client.get(production_product, headers=market_headers).json()
    first = save(market_client, market_headers, production_product, production_body)
    assert first.status_code == 201, first.text
    data = first.json()
    assert data["status"] == "completed" and data["basis"] == "seller_reported_unverified"
    assert data["product_snapshot"] == before and data["selling_unit"] == "loaf"
    assert data["result"]["batch_total"] == "45.300000"
    assert data["result"]["unit_cost"] == "4.530000" and data["result"]["unsellable_units"] == 2
    assert data["created_at"].endswith("Z") and first.headers["Cache-Control"] == "no-store"
    assert "account_id" not in first.text and "access_token" not in first.text
    market_client.patch(production_product, headers=market_headers, json={"selling_unit": "box"})
    path = production_product + "/production-records/" + data["id"]
    assert market_client.get(path, headers=market_headers).json() == data
    retry = save(market_client, market_headers, production_product, production_body)
    assert retry.status_code == 200 and retry.json() == data
    conflict = save(
        market_client, market_headers, production_product, {**production_body, "sellable_units": 9}
    )
    assert (
        conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    )
    mismatch = save(
        market_client,
        market_headers,
        production_product,
        {**production_body, "request_id": str(uuid4())},
    )
    assert (
        mismatch.status_code == 409
        and mismatch.json()["detail"]["code"] == "PRODUCTION_UNIT_MISMATCH"
    )
    # A correction retains the historical unit basis; a new batch uses the current unit.
    fixed = save(
        market_client, market_headers, production_product, correction(production_body, data)
    )
    assert fixed.status_code == 201 and fixed.json()["product_snapshot"] == before
    assert (
        save(
            market_client,
            market_headers,
            production_product,
            {**production_body, "request_id": str(uuid4()), "selling_unit": "box"},
        ).status_code
        == 201
    )


def test_correction_chain_and_current_only_history(
    market_client, market_headers, production_product, production_body
):
    original = save(market_client, market_headers, production_product, production_body).json()
    fixed_body = correction(production_body, original, sellable_units=8)
    fixed = save(market_client, market_headers, production_product, fixed_body).json()
    assert fixed["result"]["unit_cost"] == "5.662500"
    path = production_product + "/production-records"
    assert market_client.get(path + "/" + original["id"], headers=market_headers).json() == original
    assert [
        row["id"] for row in market_client.get(path, headers=market_headers).json()["items"]
    ] == [fixed["id"]]
    history = market_client.get(path + "?include_corrected=true", headers=market_headers).json()
    assert {row["id"] for row in history["items"]} == {original["id"], fixed["id"]}
    assert "request" not in history["items"][0] and "result" not in history["items"][0]
    assert save(market_client, market_headers, production_product, fixed_body).status_code == 200
    refused = save(
        market_client, market_headers, production_product, correction(production_body, original)
    )
    assert (
        refused.status_code == 409
        and refused.json()["detail"]["code"] == "RECORD_ALREADY_CORRECTED"
    )
    latest = save(
        market_client, market_headers, production_product, correction(production_body, fixed)
    )
    assert latest.status_code == 201
    assert [
        row["id"] for row in market_client.get(path, headers=market_headers).json()["items"]
    ] == [latest.json()["id"]]


def test_zero_yield_and_independence_from_inventory_and_pricing(
    market_client, market_headers, production_product, production_body
):
    material = market_client.post(
        "/api/v1/seller/materials",
        headers=market_headers,
        json={"name": "Consumed flour", "unit": "g"},
    ).json()
    material_path = "/api/v1/seller/materials/" + material["id"]
    product = market_client.get(production_product, headers=market_headers).json()
    inventory = market_client.get(production_product + "/inventory", headers=market_headers).json()
    failed = save(
        market_client,
        market_headers,
        production_product,
        {**production_body, "total_units": 0, "sellable_units": 0},
    )
    assert failed.status_code == 201 and failed.json()["result"]["unit_cost"] is None
    assert failed.json()["result"]["batch_total"] == "45.300000"
    assert market_client.get(material_path, headers=market_headers).json() == material
    assert market_client.get(production_product, headers=market_headers).json() == product
    assert (
        market_client.get(production_product + "/inventory", headers=market_headers).json()
        == inventory
    )
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Analysis)) == 0


def test_roles_ownership_and_cross_product_corrections(
    market_client, market_headers, market_account, production_product, production_body
):
    original = save(market_client, market_headers, production_product, production_body).json()
    path = production_product + "/production-records"
    buyer = market_account("production-buyer@example.com", roles=())
    admin = market_account("production-admin@example.com", roles=("admin",))
    other = market_account("production-other@example.com")
    for actor, status in (({}, 401), (buyer, 403), (admin, 403), (other, 404)):
        assert save(market_client, actor, production_product, production_body).status_code == status
        assert market_client.get(path, headers=actor).status_code == status
        assert market_client.get(path + "/" + original["id"], headers=actor).status_code == status
    another = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={"name": "Other", "product_type": "sourdough", "selling_unit": "loaf"},
    ).json()
    another_path = "/api/v1/products/" + another["id"]
    assert (
        save(
            market_client, market_headers, another_path, correction(production_body, original)
        ).status_code
        == 404
    )
    assert (
        market_client.get(
            another_path + "/production-records/" + original["id"], headers=market_headers
        ).status_code
        == 404
    )
    assert save(market_client, market_headers, another_path, production_body).status_code == 201


@pytest.mark.parametrize(
    "changes",
    [
        {"total_units": True},
        {"total_units": -1},
        {"total_units": 1000001},
        {"sellable_units": 13},
        {"sellable_units": "10"},
        {"started_on": "2026-11-02", "completed_on": "2026-11-01"},
        {"completed_on": "2999-01-01"},
        {"kind": "planned"},
        {"currency": "EUR"},
        {"status": "in_progress"},
        {"account_id": "PRIVATE_OWNER"},
        {"request_id": "PRIVATE_BAD_UUID"},
        {"correction_reason": "No prior record"},
        {"corrects_record_id": "19000000-0000-4000-8000-000000000099"},
        {"notes": "x" * 2001},
    ],
)
def test_invalid_input_is_redacted_and_atomic(
    market_client, market_headers, production_product, production_body, changes
):
    response = save(
        market_client, market_headers, production_product, {**production_body, **changes}
    )
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_OWNER" not in response.text and "PRIVATE_BAD_UUID" not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ProductionRecord)) == 0


def test_cost_labor_and_correction_reason_validation(
    market_client, market_headers, production_product, production_body
):
    for amount in (10, "NaN"):
        data = deepcopy(production_body)
        data["costs"][0]["amount"] = amount
        assert save(market_client, market_headers, production_product, data).status_code == 422
    data = deepcopy(production_body)
    data["labor"][0]["hours"] = 2
    assert save(market_client, market_headers, production_product, data).status_code == 422
    original = save(market_client, market_headers, production_product, production_body).json()
    for reason in (" ", "\x00", "x" * 2001):
        assert (
            save(
                market_client,
                market_headers,
                production_product,
                correction(production_body, original, correction_reason=reason),
            ).status_code
            == 422
        )


def test_duplicate_and_correction_concurrency(
    market_client, market_headers, production_product, production_body
):
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda _: save(market_client, market_headers, production_product, production_body),
                range(2),
            )
        )
    assert sorted(reply.status_code for reply in replies) == [200, 201]
    assert replies[0].json() == replies[1].json()
    original = replies[0].json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda request: save(market_client, market_headers, production_product, request),
                [
                    correction(production_body, original, sellable_units=8),
                    correction(production_body, original, sellable_units=9),
                ],
            )
        )
    assert sorted(reply.status_code for reply in replies) == [201, 409]
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ProductionRecord)) == 2


def test_commit_failure_leaves_key_available_for_retry(
    market_client, market_headers, production_product, production_body, market_url
):
    def fail(db):
        if any(isinstance(row, ProductionRecord) for row in db.new):
            raise RuntimeError("Synthetic production commit failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert (
                save(client, market_headers, production_product, production_body).status_code == 500
            )
    finally:
        event.remove(Session, "before_commit", fail)
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ProductionRecord)) == 0
    assert (
        save(market_client, market_headers, production_product, production_body).status_code == 201
    )


def test_pagination_restart_and_migration_guards(
    market_client, market_headers, production_product, production_body, market_url
):
    first = save(market_client, market_headers, production_product, production_body).json()
    save(
        market_client,
        market_headers,
        production_product,
        {**production_body, "request_id": str(uuid4()), "label": "Another completed batch"},
    )
    path = production_product + "/production-records"
    page = market_client.get(path + "?limit=1&offset=1", headers=market_headers).json()
    assert [row["id"] for row in page["items"]] == [first["id"]]
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="production records"):
        command.downgrade(config, "0021")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(path + "/" + first["id"], headers=market_headers).json() == first
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_empty_migration_preserves_existing_product_and_analysis(
    market_client, market_headers, production_product, payload
):
    original = market_client.post(
        production_product + "/analyses", headers=market_headers, json=payload
    ).json()
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0021")
    command.upgrade(config, "head")
    command.check(config)
    assert (
        market_client.get(
            production_product + "/analyses/" + original["id"], headers=market_headers
        ).json()
        == original
    )
    assert (
        market_client.get(
            production_product + "/production-records", headers=market_headers
        ).json()["items"]
        == []
    )


def test_openapi_private_decimal_contract_and_bounds(
    market_client, market_headers, production_product
):
    schema = market_client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        if "/production-records" in path:
            assert all(method["security"] == [{"HTTPBearer": []}] for method in methods.values())
    models = schema["components"]["schemas"]
    assert models["RecordedCost"]["properties"]["amount"]["type"] == "string"
    assert models["RecordedLabor"]["properties"]["hours"]["type"] == "string"
    assert "result" not in models["ProductionSummary"]["properties"]
    path = production_product + "/production-records"
    for query in ("limit=101", "offset=-1", "include_corrected=invalid"):
        assert market_client.get(path + "?" + query, headers=market_headers).status_code == 422
    assert market_client.get(path + "/" + str(uuid4()), headers=market_headers).status_code == 404
