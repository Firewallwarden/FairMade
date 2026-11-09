"""Ledger authorization, exact changes, immutable retries and transaction boundaries."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from fairmade.evidence import today
from fairmade.main import create_app
from fairmade.models import Material, MaterialMovement

BASE = "/api/v1/seller/materials"
BACKEND = Path(__file__).parents[2]


def body(material, **changes):
    return {
        "expected_revision": material["revision"],
        "request_id": str(uuid4()),
        "kind": "receipt",
        "quantity": "1",
        "unit": "kg",
        "occurred_on": today().isoformat(),
        "reason": "Synthetic manual stock receipt",
        **changes,
    }


def record(client, headers, material, **changes):
    return client.post(
        BASE + "/" + material["id"] + "/movements", headers=headers, json=body(material, **changes)
    )


def current(client, headers, material):
    return client.get(BASE + "/" + material["id"], headers=headers).json()


def test_material_starts_at_zero_and_events_reconcile_exactly(
    market_client, market_headers, material
):
    assert material["on_hand"] == "0.000000" and material["revision"] == 1
    assert material["basis"] == "seller_reported_unverified"
    path = BASE + "/" + material["id"]
    assert market_client.get(path + "/movements", headers=market_headers).json()["items"] == []
    receipt = record(market_client, market_headers, material, quantity="1.25")
    assert receipt.status_code == 201, receipt.text
    assert receipt.json()["before"] == "0.000000"
    assert receipt.json()["after"] == "1250.000000" and receipt.json()["delta"] == "1250.000000"
    assert receipt.json()["unit"] == "g" and receipt.json()["revision"] == 2
    for kind, quantity, after in (
        ("usage", "250", "1000.000000"),
        ("waste", "0.000001", "999.999999"),
        ("adjustment", "900", "900.000000"),
        ("adjustment", "0", "0.000000"),
    ):
        response = record(
            market_client,
            market_headers,
            current(market_client, market_headers, material),
            kind=kind,
            quantity=quantity,
            unit="g",
        )
        assert response.status_code == 201 and response.json()["after"] == after
    events = market_client.get(path + "/movements", headers=market_headers).json()["items"]
    assert [row["revision"] for row in events] == [6, 5, 4, 3, 2]
    assert sum((Decimal(row["delta"]) for row in events), Decimal(0)) == 0
    assert current(market_client, market_headers, material)["on_hand"] == "0.000000"
    assert receipt.headers["Cache-Control"] == "no-store"
    assert "account_id" not in receipt.text and "on_hand_micros" not in receipt.text


def test_physical_count_confirmation_and_backdated_event_use_posting_order(
    market_client, market_headers, material
):
    first = record(market_client, market_headers, material)
    latest = current(market_client, market_headers, material)
    confirmation = record(
        market_client, market_headers, latest, kind="adjustment", quantity="1000", unit="g"
    )
    assert confirmation.status_code == 201 and confirmation.json()["delta"] == "0.000000"
    latest = current(market_client, market_headers, material)
    backdated = record(
        market_client,
        market_headers,
        latest,
        kind="waste",
        quantity="10",
        unit="g",
        occurred_on=(today() - timedelta(days=10)).isoformat(),
    )
    assert backdated.status_code == 201 and backdated.json()["after"] == "990.000000"
    assert first.json()["after"] == "1000.000000"


def test_metadata_edits_preserve_movement_identity_and_retry_snapshot(
    market_client, market_headers, material
):
    request = body(material)
    path = BASE + "/" + material["id"]
    first = market_client.post(path + "/movements", headers=market_headers, json=request)
    latest = current(market_client, market_headers, material)
    edited = market_client.put(
        path,
        headers=market_headers,
        json={"name": "Renamed flour", "notes": None, "expected_revision": latest["revision"]},
    )
    assert edited.status_code == 200 and edited.json()["revision"] == 3
    assert edited.json()["on_hand"] == "1000.000000"
    assert edited.json()["created_at"] == material["created_at"]
    retry = market_client.post(path + "/movements", headers=market_headers, json=request)
    assert retry.status_code == 200 and retry.json() == first.json()
    assert retry.json()["material_name"] == "PRIVATE_FLOUR"
    assert current(market_client, market_headers, material) == edited.json()
    assert (
        market_client.get(path + "/movements/" + first.json()["id"], headers=market_headers).json()
        == first.json()
    )
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(MaterialMovement)) == 1


def test_idempotency_conflicts_stale_writes_and_decimal_equivalent_retry(
    market_client, market_headers, material
):
    request = body(material)
    path = BASE + "/" + material["id"]
    first = market_client.post(path + "/movements", headers=market_headers, json=request)
    same = market_client.post(
        path + "/movements", headers=market_headers, json={**request, "quantity": "1.000000"}
    )
    assert same.status_code == 200 and same.json() == first.json()
    conflict = market_client.post(
        path + "/movements", headers=market_headers, json={**request, "reason": "Changed reason"}
    )
    assert (
        conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    )
    assert (
        record(market_client, market_headers, material).json()["detail"]["code"]
        == "REVISION_CONFLICT"
    )
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={"name": "Stale", "expected_revision": 1},
        ).status_code
        == 409
    )


def test_underflow_unit_mismatch_and_normalized_limits_do_not_write_events(
    market_client, market_headers, material
):
    for changes, status, code in (
        ({"kind": "usage", "quantity": "1", "unit": "g"}, 409, "INSUFFICIENT_MATERIAL"),
        ({"kind": "waste", "quantity": "1", "unit": "g"}, 409, "INSUFFICIENT_MATERIAL"),
        ({"unit": "l"}, 422, "UNIT_MISMATCH"),
        ({"quantity": "1000000000", "unit": "kg"}, 422, "QUANTITY_LIMIT"),
    ):
        response = record(market_client, market_headers, material, **changes)
        assert response.status_code == status and response.json()["detail"]["code"] == code
    maximum = record(market_client, market_headers, material, quantity="1000000000", unit="g")
    assert maximum.status_code == 201
    latest = current(market_client, market_headers, material)
    exceeded = record(market_client, market_headers, latest, quantity="0.000001", unit="g")
    assert exceeded.status_code == 409 and exceeded.json()["detail"]["code"] == "QUANTITY_LIMIT"
    assert current(market_client, market_headers, material) == latest
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(MaterialMovement)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 1},
        {"quantity": "-1"},
        {"quantity": "NaN"},
        {"quantity": "Infinity"},
        {"quantity": "0"},
        {"quantity": "0.0000001"},
        {"quantity": "0.5", "unit": "item"},
        {"unit": "cup"},
        {"expected_revision": True},
        {"expected_revision": "1"},
        {"request_id": "PRIVATE_BAD_REQUEST"},
        {"reason": " "},
        {"reason": "x" * 2001},
        {"reason": "\x00"},
        {"purchase_cost": "PRIVATE_COST"},
        {"account_id": "PRIVATE_OWNER"},
        {"occurred_on": "2999-01-01"},
    ],
)
def test_invalid_requests_are_bounded_redacted_and_leave_stock_unchanged(
    market_client, market_headers, material, changes
):
    response = record(market_client, market_headers, material, **changes)
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_BAD_REQUEST" not in response.text and "PRIVATE_COST" not in response.text
    assert "PRIVATE_OWNER" not in response.text
    assert all("input" not in item for item in response.json()["detail"])
    assert current(market_client, market_headers, material) == material


def test_owner_and_role_boundaries_and_cross_material_movement_lookup(
    market_client, market_headers, market_account, material
):
    event_record = record(market_client, market_headers, material).json()
    path = BASE + "/" + material["id"]
    buyer = market_account("material-buyer@example.com", roles=())
    admin = market_account("material-admin@example.com", roles=("admin",))
    other = market_account("material-other@example.com")
    for actor, status in (({}, 401), (buyer, 403), (admin, 403), (other, 404)):
        for method, suffix, data in (
            ("GET", "", None),
            ("PUT", "", {"name": "Cannot rename", "expected_revision": 2}),
            ("GET", "/movements", None),
            ("POST", "/movements", body(material)),
            ("GET", "/movements/" + event_record["id"], None),
        ):
            result = market_client.request(method, path + suffix, headers=actor, json=data)
            assert result.status_code == status, result.text
    assert market_client.get(BASE, headers=other).json()["items"] == []
    assert (
        market_client.post(BASE, headers=buyer, json={"name": "Forbidden", "unit": "g"}).status_code
        == 403
    )
    another = market_client.post(
        BASE, headers=market_headers, json={"name": "Another", "unit": "g"}
    ).json()
    assert (
        market_client.get(
            BASE + "/" + another["id"] + "/movements/" + event_record["id"], headers=market_headers
        ).status_code
        == 404
    )
    # The same retry key is scoped to each material, not to another user's records.
    assert (
        record(
            market_client, market_headers, another, request_id=event_record["request_id"]
        ).status_code
        == 201
    )


def test_names_are_unique_per_seller_and_units_cannot_change(
    market_client, market_headers, market_account, material
):
    duplicate = market_client.post(
        BASE, headers=market_headers, json={"name": " private_flour ", "unit": "ml"}
    )
    assert duplicate.status_code == 409
    other = market_account("material-name-owner@example.com")
    assert (
        market_client.post(
            BASE, headers=other, json={"name": "PRIVATE_FLOUR", "unit": "ml"}
        ).status_code
        == 201
    )
    second = market_client.post(
        BASE, headers=market_headers, json={"name": "Second", "unit": "g"}
    ).json()
    assert (
        market_client.put(
            BASE + "/" + second["id"],
            headers=market_headers,
            json={"name": material["name"], "expected_revision": 1},
        ).status_code
        == 409
    )
    assert (
        market_client.put(
            BASE + "/" + material["id"],
            headers=market_headers,
            json={"name": material["name"], "unit": "ml", "expected_revision": 1},
        ).status_code
        == 422
    )


def test_whole_item_inventory(market_client, market_headers):
    material = market_client.post(
        BASE, headers=market_headers, json={"name": "Cartons", "unit": "item"}
    ).json()
    assert (
        record(market_client, market_headers, material, quantity="3", unit="item").json()["after"]
        == "3.000000"
    )
    assert (
        record(
            market_client,
            market_headers,
            current(market_client, market_headers, material),
            quantity="0.1",
            unit="item",
        ).status_code
        == 422
    )


def test_concurrent_duplicate_creates_and_retries_apply_only_once(
    market_client, market_headers, material
):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: market_client.post(
                    BASE, headers=market_headers, json={"name": "Concurrent", "unit": "ml"}
                ),
                range(2),
            )
        )
    assert sorted(result.status_code for result in results) == [201, 409]
    request = body(material)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: market_client.post(
                    BASE + "/" + material["id"] + "/movements", headers=market_headers, json=request
                ),
                range(2),
            )
        )
    assert sorted(result.status_code for result in results) == [200, 201]
    assert results[0].json() == results[1].json()
    assert current(market_client, market_headers, material)["on_hand"] == "1000.000000"


def test_concurrent_withdrawals_cannot_overspend_material(market_client, market_headers, material):
    record(market_client, market_headers, material, quantity="1", unit="g")
    latest = current(market_client, market_headers, material)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda kind: record(
                    market_client, market_headers, latest, kind=kind, quantity="0.75", unit="g"
                ),
                ["usage", "waste"],
            )
        )
    assert sorted(result.status_code for result in results) == [201, 409]
    after = current(market_client, market_headers, material)
    assert after["on_hand"] == "0.250000"
    refused = record(market_client, market_headers, after, kind="usage", quantity="0.75", unit="g")
    assert (
        refused.status_code == 409 and refused.json()["detail"]["code"] == "INSUFFICIENT_MATERIAL"
    )


def test_failed_commit_rolls_back_balance_revision_and_event(
    market_client, market_headers, material, market_url
):
    def fail(db):
        if any(isinstance(row, MaterialMovement) for row in db.new):
            raise RuntimeError("Synthetic ledger commit failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert record(client, market_headers, material).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert current(market_client, market_headers, material) == material
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(MaterialMovement)) == 0
    assert record(market_client, market_headers, material).status_code == 201


def test_ledger_and_recipe_costing_do_not_mutate_each_others_state(
    market_client, market_headers, material, market_record
):
    product_path = market_record["path"]
    inventory_before = market_client.get(product_path + "/inventory", headers=market_headers).json()
    analyses_before = market_client.get(product_path + "/analyses", headers=market_headers).json()
    record(market_client, market_headers, material)
    assert (
        market_client.get(product_path + "/inventory", headers=market_headers).json()
        == inventory_before
    )
    assert (
        market_client.get(product_path + "/analyses", headers=market_headers).json()
        == analyses_before
    )
    recipe = json.loads((BACKEND / "examples/recipes/sourdough.json").read_text(encoding="utf-8"))
    recipe["ingredients"][0]["label"] = material["name"]
    assert (
        market_client.post(
            product_path + "/recipe", headers=market_headers, json=recipe
        ).status_code
        == 201
    )
    balance_before = current(market_client, market_headers, material)
    assert (
        market_client.post(
            product_path + "/recipe/costings",
            headers=market_headers,
            json={"expected_revision": 1, "request_id": str(uuid4())},
        ).status_code
        == 201
    )
    assert current(market_client, market_headers, material) == balance_before
    assert (
        market_client.get(product_path + "/inventory", headers=market_headers).json()
        == inventory_before
    )


def test_pages_restart_metadata_and_history_downgrade_guard(
    market_client, market_headers, material, market_url
):
    first = record(market_client, market_headers, material).json()
    second = record(
        market_client,
        market_headers,
        current(market_client, market_headers, material),
        kind="waste",
        quantity="1",
        unit="g",
    ).json()
    path = BASE + "/" + material["id"]
    page = market_client.get(path + "/movements?limit=1&offset=1", headers=market_headers).json()
    assert [row["id"] for row in page["items"]] == [first["id"]]
    assert second["revision"] > first["revision"]
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="material movement records"):
        command.downgrade(config, "0020")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert (
            restarted.get(path + "/movements/" + first["id"], headers=market_headers).json()
            == first
        )
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_blank_upgrade_preserves_product_analysis_and_catalog_guard(
    market_client, market_headers, payload
):
    product = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={"name": "Existing", "product_type": "eggs", "selling_unit": "dozen"},
    ).json()
    product_path = "/api/v1/products/" + product["id"]
    analysis = market_client.post(
        product_path + "/analyses", headers=market_headers, json=payload
    ).json()
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0020")
    command.upgrade(config, "head")
    command.check(config)
    assert (
        market_client.get(
            product_path + "/analyses/" + analysis["id"], headers=market_headers
        ).json()
        == analysis
    )
    assert market_client.get(BASE, headers=market_headers).json()["items"] == []
    market_client.post(BASE, headers=market_headers, json={"name": "Protected", "unit": "g"})
    with pytest.raises(RuntimeError, match="material records"):
        command.downgrade(config, "base")
    command.check(config)


def test_openapi_decimal_strings_privacy_and_pagination(market_client, market_headers, material):
    schema = market_client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        if "/materials" in path:
            assert path.startswith(BASE)
            assert all(method["security"] == [{"HTTPBearer": []}] for method in methods.values())
    properties = schema["components"]["schemas"]["MovementRequest"]["properties"]
    assert properties["quantity"]["type"] == "string"
    assert "purchase_cost" not in properties
    for suffix in ("?limit=101", "?offset=-1", "?offset=9223372036854775808"):
        assert market_client.get(BASE + suffix, headers=market_headers).status_code == 422
    assert market_client.get(BASE + "/" + str(uuid4()), headers=market_headers).status_code == 404
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Material)) == 1
