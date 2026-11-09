"""Private revisioned recipes, immutable provenance and atomic pricing integration."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
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
from fairmade.models import Analysis, ProductRecipe, RecipeCosting

BACKEND = Path(__file__).parents[2]


def create_recipe(client, product, headers, body):
    return client.post(product + "/recipe", headers=headers, json=body)


def save_costing(client, product, headers, revision=1, request_id=None):
    return client.post(
        product + "/recipe/costings",
        headers=headers,
        json={"expected_revision": revision, "request_id": request_id or str(uuid4())},
    )


def test_recipe_creates_only_on_explicit_post_and_requires_revision_for_edit(
    market_client, market_headers, recipe_product, recipe_body
):
    path = recipe_product + "/recipe"
    assert market_client.get(path, headers=market_headers).status_code == 404
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ProductRecipe)) == 0
    created = create_recipe(market_client, recipe_product, market_headers, recipe_body)
    assert created.status_code == 201, created.text
    before = created.json()
    assert before["revision"] == 1 and before["content"]["name"] == recipe_body["name"]
    assert before["created_at"].endswith("Z")
    assert (
        create_recipe(market_client, recipe_product, market_headers, recipe_body).status_code == 409
    )
    updated = market_client.put(
        path,
        headers=market_headers,
        json={**recipe_body, "name": "New recipe", "expected_revision": 1},
    )
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    assert updated.json()["created_at"] == before["created_at"]
    stale = market_client.put(
        path, headers=market_headers, json={**recipe_body, "expected_revision": 1}
    )
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "REVISION_CONFLICT"
    assert market_client.get(path, headers=market_headers).json() == updated.json()
    assert updated.headers["Cache-Control"] == "no-store"


def test_costing_saves_standard_analysis_without_stock_or_price_changes(
    market_client, market_headers, recipe_product, recipe_body
):
    product_before = market_client.get(recipe_product, headers=market_headers).json()
    create_recipe(market_client, recipe_product, market_headers, recipe_body)
    response = save_costing(market_client, recipe_product, market_headers)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["recipe_snapshot"] == recipe_body
    assert record["result"]["materials_total"] == "10.300000"
    assert record["result"]["basis"] == "seller_reported_unverified"
    analysis = market_client.get(
        recipe_product + "/analyses/" + record["pricing_analysis_id"], headers=market_headers
    ).json()
    assert analysis["result"]["costs"]["batch_total"] == "45.300000"
    assert analysis["product_snapshot"] == product_before
    assert len(analysis["inputs"]["costs"]) == 4
    assert market_client.get(recipe_product, headers=market_headers).json() == product_before
    assert not market_client.get(recipe_product + "/inventory", headers=market_headers).json()[
        "configured"
    ]
    assert market_client.get("/api/v1/marketplace/listings").json()["items"] == []
    assert (
        record
        == market_client.get(
            recipe_product + "/recipe/costings/" + record["id"], headers=market_headers
        ).json()
    )
    # Existing pricing reviews can select the generated analysis explicitly.
    review = market_client.post(
        recipe_product + "/pricing-reviews",
        headers=market_headers,
        json={"pricing_analysis_id": analysis["id"], "quality_evaluation_ids": []},
    )
    assert review.status_code == 201, review.text
    assert response.headers["Cache-Control"] == "no-store"


def test_costing_retry_preserves_snapshot_after_recipe_and_product_edits(
    market_client, market_headers, recipe_product, recipe_body
):
    create_recipe(market_client, recipe_product, market_headers, recipe_body)
    request_id = str(uuid4())
    first = save_costing(market_client, recipe_product, market_headers, request_id=request_id)
    changed = deepcopy(recipe_body)
    changed["ingredients"][0]["purchase_cost"] = "40"
    assert (
        market_client.put(
            recipe_product + "/recipe",
            headers=market_headers,
            json={**changed, "expected_revision": 1},
        ).status_code
        == 200
    )
    assert (
        market_client.patch(
            recipe_product, headers=market_headers, json={"name": "Edited product"}
        ).status_code
        == 200
    )
    retry = save_costing(market_client, recipe_product, market_headers, request_id=request_id)
    assert retry.status_code == 200 and retry.json() == first.json()
    assert (
        save_costing(
            market_client, recipe_product, market_headers, revision=2, request_id=request_id
        ).json()["detail"]["code"]
        == "IDEMPOTENCY_CONFLICT"
    )
    stale = save_costing(market_client, recipe_product, market_headers)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "REVISION_CONFLICT"
    second = save_costing(market_client, recipe_product, market_headers, revision=2).json()
    assert second["result"]["materials_total"] == "20.300000"
    assert first.json()["recipe_snapshot"] == recipe_body
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(RecipeCosting)) == 2
        assert db.scalar(select(func.count()).select_from(Analysis)) == 2


def test_auth_ownership_and_cross_product_costing_scope(
    market_client, market_account, market_headers, recipe_product, recipe_body
):
    create_recipe(market_client, recipe_product, market_headers, recipe_body)
    record = save_costing(market_client, recipe_product, market_headers).json()
    routes = [
        ("GET", "/recipe", None),
        ("POST", "/recipe", recipe_body),
        ("PUT", "/recipe", {**recipe_body, "expected_revision": 1}),
        ("GET", "/recipe/costings", None),
        ("POST", "/recipe/costings", {"expected_revision": 1, "request_id": str(uuid4())}),
        ("GET", "/recipe/costings/" + record["id"], None),
    ]
    buyer = market_account("recipe-buyer@example.com", roles=())
    admin = market_account("recipe-admin@example.com", roles=("admin",))
    other = market_account("other-recipe-seller@example.com")
    for headers, status in (({}, 401), (buyer, 403), (admin, 403), (other, 404)):
        for method, suffix, body in routes:
            response = market_client.request(
                method, recipe_product + suffix, headers=headers, json=body
            )
            assert response.status_code == status, response.text
    another = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={"name": "Other", "product_type": "eggs", "selling_unit": "dozen"},
    ).json()
    assert (
        market_client.get(
            "/api/v1/products/" + another["id"] + "/recipe/costings/" + record["id"],
            headers=market_headers,
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "change",
    [
        {"currency": "EUR"},
        {"sellable_units": 0},
        {"sellable_units": True},
        {"ingredients": []},
        {"other_costs": [{"label": "Duplicate materials", "category": "materials", "amount": "1"}]},
        {"instructions": "x" * 10001},
        {"supplier_quote_id": "PRIVATE_QUOTE_ID"},
        {"account_id": "PRIVATE_ACCOUNT_ID"},
    ],
)
def test_invalid_recipes_are_redacted_and_do_not_create_records(
    market_client, market_headers, recipe_product, recipe_body, change
):
    response = create_recipe(
        market_client, recipe_product, market_headers, {**recipe_body, **change}
    )
    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_QUOTE_ID" not in response.text and "PRIVATE_ACCOUNT_ID" not in response.text
    assert all("input" not in item for item in response.json()["detail"])
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ProductRecipe)) == 0


def test_future_dates_duplicate_labels_and_allocation_overflow_are_rejected(
    market_client, market_headers, recipe_product, recipe_body
):
    future = deepcopy(recipe_body)
    future["ingredients"][0]["cost_recorded_on"] = (today() + timedelta(days=1)).isoformat()
    assert create_recipe(market_client, recipe_product, market_headers, future).status_code == 422
    duplicate = deepcopy(recipe_body)
    duplicate["ingredients"][1]["label"] = duplicate["ingredients"][0]["label"].upper()
    assert (
        create_recipe(market_client, recipe_product, market_headers, duplicate).status_code == 422
    )
    overflow = deepcopy(recipe_body)
    overflow["ingredients"][0]["purchase_quantity"]["value"] = "0.000001"
    overflow["ingredients"][0]["purchase_cost"] = "1000000000"
    response = create_recipe(market_client, recipe_product, market_headers, overflow)
    assert (
        response.status_code == 422 and response.json()["detail"]["code"] == "COST_LIMIT_EXCEEDED"
    )
    assert market_client.get(recipe_product + "/recipe", headers=market_headers).status_code == 404


def test_concurrent_create_edit_and_exact_costing_retries(
    market_client, market_headers, recipe_product, recipe_body
):
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(
            pool.map(
                lambda _: create_recipe(market_client, recipe_product, market_headers, recipe_body),
                range(2),
            )
        )
    assert sorted(response.status_code for response in created) == [201, 409]
    with ThreadPoolExecutor(max_workers=2) as pool:
        edited = list(
            pool.map(
                lambda name: market_client.put(
                    recipe_product + "/recipe",
                    headers=market_headers,
                    json={**recipe_body, "name": name, "expected_revision": 1},
                ),
                ["Concurrent A", "Concurrent B"],
            )
        )
    assert sorted(response.status_code for response in edited) == [200, 409]
    request_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: save_costing(
                    market_client, recipe_product, market_headers, revision=2, request_id=request_id
                ),
                range(2),
            )
        )
    assert sorted(response.status_code for response in results) == [200, 201]
    assert results[0].json() == results[1].json()
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Analysis)) == 1
        assert db.scalar(select(func.count()).select_from(RecipeCosting)) == 1


def test_costing_and_edit_race_preserves_the_matching_revision(
    market_client, market_headers, recipe_product, recipe_body
):
    create_recipe(market_client, recipe_product, market_headers, recipe_body)
    changed = {**recipe_body, "name": "After edit", "expected_revision": 1}
    with ThreadPoolExecutor(max_workers=2) as pool:
        snapshot = pool.submit(save_costing, market_client, recipe_product, market_headers)
        edit = pool.submit(
            market_client.put, recipe_product + "/recipe", headers=market_headers, json=changed
        )
        snapshot, edit = snapshot.result(), edit.result()
    assert edit.status_code == 200
    assert snapshot.status_code in (201, 409)
    if snapshot.status_code == 201:
        assert snapshot.json()["recipe_revision"] == 1
        assert snapshot.json()["recipe_snapshot"] == recipe_body


def test_failed_costing_commit_rolls_back_analysis_and_provenance(
    market_client, market_headers, recipe_product, recipe_body, market_url
):
    create_recipe(market_client, recipe_product, market_headers, recipe_body)

    def fail(db):
        if any(isinstance(row, RecipeCosting) for row in db.new):
            raise RuntimeError("Synthetic costing commit failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert save_costing(client, recipe_product, market_headers).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Analysis)) == 0
        assert db.scalar(select(func.count()).select_from(RecipeCosting)) == 0
        assert db.get(ProductRecipe, recipe_product.rsplit("/", 1)[1]).revision == 1
    assert save_costing(market_client, recipe_product, market_headers).status_code == 201


def test_history_pagination_restart_metadata_and_downgrade_guard(
    market_client, market_headers, recipe_product, recipe_body, market_url
):
    create_recipe(market_client, recipe_product, market_headers, recipe_body)
    first = save_costing(market_client, recipe_product, market_headers).json()
    save_costing(market_client, recipe_product, market_headers)
    page = market_client.get(
        recipe_product + "/recipe/costings?limit=1&offset=1", headers=market_headers
    )
    assert [row["id"] for row in page.json()["items"]] == [first["id"]]
    assert "recipe_snapshot" not in page.text
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="recipe costing records"):
        command.downgrade(config, "0019")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert (
            restarted.get(
                recipe_product + "/recipe/costings/" + first["id"], headers=market_headers
            ).json()
            == first
        )
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_recipe_only_downgrade_guard_and_empty_roundtrip(
    market_client, market_headers, recipe_product, recipe_body, payload
):
    config = Config(str(BACKEND / "alembic.ini"))
    before = market_client.get(recipe_product, headers=market_headers).json()
    command.downgrade(config, "0019")
    historical = market_client.post(
        recipe_product + "/analyses", headers=market_headers, json=payload
    )
    assert historical.status_code == 201
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get(recipe_product, headers=market_headers).json() == before
    assert (
        market_client.get(
            recipe_product + "/analyses/" + historical.json()["id"], headers=market_headers
        ).json()
        == historical.json()
    )
    assert market_client.get(recipe_product + "/recipe", headers=market_headers).status_code == 404
    create_recipe(market_client, recipe_product, market_headers, recipe_body)
    with pytest.raises(RuntimeError, match="recipe records"):
        command.downgrade(config, "base")
    command.check(config)


def test_missing_recipe_bad_revision_and_bounded_history(
    market_client, market_headers, recipe_product, recipe_body
):
    assert save_costing(market_client, recipe_product, market_headers).status_code == 404
    assert (
        market_client.put(
            recipe_product + "/recipe",
            headers=market_headers,
            json={**recipe_body, "expected_revision": 1},
        ).status_code
        == 404
    )
    create_recipe(market_client, recipe_product, market_headers, recipe_body)
    for revision in (0, True, "1"):
        assert (
            market_client.post(
                recipe_product + "/recipe/costings",
                headers=market_headers,
                json={"expected_revision": revision, "request_id": str(uuid4())},
            ).status_code
            == 422
        )
    for query in ("limit=101", "offset=-1"):
        assert (
            market_client.get(
                recipe_product + "/recipe/costings?" + query, headers=market_headers
            ).status_code
            == 422
        )
    assert (
        market_client.post(
            recipe_product + "/recipe/costings",
            headers=market_headers,
            json={"expected_revision": 1, "request_id": "PRIVATE_INVALID_ID"},
        ).status_code
        == 422
    )


def test_openapi_describes_private_recipe_paths_and_decimal_strings(market_client):
    schema = market_client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        if "/recipe" in path:
            assert all(method["security"] == [{"HTTPBearer": []}] for method in methods.values())
    models = schema["components"]["schemas"]
    assert models["Ingredient"]["properties"]["purchase_cost"]["type"] == "string"
    quantity_schema = models["Ingredient"]["properties"]["quantity"]["$ref"].rsplit("/", 1)[1]
    assert models[quantity_schema]["properties"]["value"]["type"] == "string"
