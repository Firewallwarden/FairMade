"""Persisted observations, selected evidence reports, isolation, and migrations."""

import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import PriceComparison, PriceObservation

BACKEND = Path(__file__).parents[2]


def save(client, headers, path, details):
    response = client.post(path + "/price-observations", headers=headers, json=details)
    assert response.status_code == 201, response.text
    return response.json()


def request_for(*observations):
    return {
        "observation_ids": [item["id"] for item in observations],
        "target_quantity": {"value": "100", "unit": "g"},
    }


def endpoints(path, observation_body, request):
    return [
        ("post", path + "/price-observations", observation_body),
        ("get", path + "/price-observations", None),
        ("get", path + "/price-observations/" + str(uuid4()), None),
        ("post", path + "/price-comparisons", request),
        ("get", path + "/price-comparisons", None),
        ("get", path + "/price-comparisons/" + str(uuid4()), None),
    ]


def test_observation_and_report_preserve_provenance_and_snapshots(
    comparison_client,
    comparison_headers,
    comparison_url,
    product_path,
    observation_body,
    monkeypatch,
):
    saved = save(comparison_client, comparison_headers, product_path, observation_body)
    assert saved["details"] == observation_body
    assert saved["basis"] == "seller_reported_unverified"
    assert saved["created_at"].endswith("Z")
    request = request_for(saved)
    response = comparison_client.post(
        product_path + "/price-comparisons", headers=comparison_headers, json=request
    )
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["as_of_date"] == "2026-01-31"
    assert report["comparison_version"] == "finished-product-comparison-v1"
    assert report["basis"] == "seller_reported_unverified"
    assert report["request_snapshot"]["max_age_days"] == 30
    assert report["product_snapshot"]["name"] == "Synthetic loaf"
    result = report["result"]
    assert result["rows"][0]["details"] == observation_body
    assert result["rows"][0]["observation_id"] == saved["id"]
    assert result["selected_price_range"] == {
        "included_count": 1,
        "excluded_count": 0,
        "minimum": "1.600000",
        "maximum": "1.600000",
    }
    assert "QUALITY_NOT_EVALUATED" in result["warnings"]
    assert (
        comparison_client.patch(
            product_path, headers=comparison_headers, json={"name": "Renamed"}
        ).status_code
        == 200
    )
    monkeypatch.setattr("fairmade.comparisons.routes.today", lambda: date(2027, 1, 31))

    def no_recalculation(*_args):
        raise AssertionError("History must not re-evaluate")

    monkeypatch.setattr("fairmade.comparisons.routes.compare", no_recalculation)
    report_url = product_path + "/price-comparisons/" + report["id"]
    observation_url = product_path + "/price-observations/" + saved["id"]
    assert comparison_client.get(report_url, headers=comparison_headers).json() == report
    assert comparison_client.get(observation_url, headers=comparison_headers).json() == saved
    with TestClient(create_app(comparison_url)) as restarted:
        assert restarted.get(report_url, headers=comparison_headers).json() == report
        assert restarted.get(observation_url, headers=comparison_headers).json() == saved
    for url in (report_url, observation_url):
        for method in ("put", "patch", "delete"):
            assert (
                comparison_client.request(
                    method, url, headers=comparison_headers, json={}
                ).status_code
                == 405
            )


def test_report_selects_explicit_evidence_and_preserves_request_order(
    comparison_client,
    comparison_headers,
    product_path,
    observation_body,
):
    first = save(comparison_client, comparison_headers, product_path, observation_body)
    second = save(
        comparison_client, comparison_headers, product_path, {**observation_body, "price": "10"}
    )
    save(comparison_client, comparison_headers, product_path, {**observation_body, "price": "1000"})
    response = comparison_client.post(
        product_path + "/price-comparisons",
        headers=comparison_headers,
        json=request_for(second, first),
    )
    assert response.status_code == 201
    result = response.json()["result"]
    assert [row["observation_id"] for row in result["rows"]] == [second["id"], first["id"]]
    assert result["selected_price_range"]["maximum"] == "2.000000"
    assert result["selected_price_range"]["included_count"] == 2


def test_reports_have_null_range_when_all_evidence_is_excluded(
    comparison_client,
    comparison_headers,
    product_path,
    observation_body,
):
    stale = save(
        comparison_client,
        comparison_headers,
        product_path,
        {
            **observation_body,
            "observed_on": "2025-01-01",
        },
    )
    incompatible = save(
        comparison_client,
        comparison_headers,
        product_path,
        {
            **observation_body,
            "quantity": {"value": "1", "unit": "loaf"},
        },
    )
    response = comparison_client.post(
        product_path + "/price-comparisons",
        headers=comparison_headers,
        json=request_for(stale, incompatible),
    )
    assert response.status_code == 201
    result = response.json()["result"]
    assert result["selected_price_range"] == {
        "included_count": 0,
        "excluded_count": 2,
        "minimum": None,
        "maximum": None,
    }
    assert result["rows"][0]["normalized_price"] == "1.600000"
    assert result["rows"][1]["normalized_price"] is None
    assert "NO_FRESH_QUANTITY_COMPARABLE_OBSERVATIONS" in result["warnings"]


@pytest.mark.parametrize("authorization", [None, "Bearer bad", "Basic bad"])
def test_authentication_on_every_route(
    comparison_client,
    product_path,
    observation_body,
    authorization,
):
    headers = {"Authorization": authorization} if authorization else {}
    request = {"observation_ids": [str(uuid4())], "target_quantity": {"value": "100", "unit": "g"}}
    for method, path, body in endpoints(product_path, observation_body, request):
        assert (
            comparison_client.request(method, path, headers=headers, json=body).status_code == 401
        )


@pytest.mark.parametrize("roles,pending", [((), False), ((), True), (("admin",), False)])
def test_only_sellers_can_use_price_evidence(
    comparison_client,
    product_path,
    account_factory,
    observation_body,
    roles,
    pending,
):
    headers = account_factory("buyer@example.com", roles)
    if pending:
        assert (
            comparison_client.post(
                "/api/v1/seller-applications", headers=headers, json={}
            ).status_code
            == 201
        )
    request = {"observation_ids": [str(uuid4())], "target_quantity": {"value": "100", "unit": "g"}}
    for method, path, body in endpoints(product_path, observation_body, request):
        response = comparison_client.request(method, path, headers=headers, json=body)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "SELLER_REQUIRED"


def test_ownership_and_cross_product_evidence_isolation(
    comparison_client,
    comparison_headers,
    product_path,
    account_factory,
    observation_body,
):
    first = save(comparison_client, comparison_headers, product_path, observation_body)
    report = comparison_client.post(
        product_path + "/price-comparisons",
        headers=comparison_headers,
        json=request_for(first),
    ).json()
    other = account_factory("other@example.com", ("seller",))
    for method, path, body in endpoints(product_path, observation_body, request_for(first)):
        assert comparison_client.request(method, path, headers=other, json=body).status_code == 404
    for path in (
        product_path + "/price-observations/" + first["id"],
        product_path + "/price-comparisons/" + report["id"],
    ):
        assert comparison_client.get(path, headers=other).status_code == 404
    second_product = comparison_client.post(
        "/api/v1/products",
        headers=comparison_headers,
        json={
            "name": "Another owned loaf",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    ).json()
    second_path = "/api/v1/products/" + second_product["id"]
    assert (
        comparison_client.get(
            second_path + "/price-observations/" + first["id"],
            headers=comparison_headers,
        ).status_code
        == 404
    )
    assert (
        comparison_client.get(
            second_path + "/price-comparisons/" + report["id"],
            headers=comparison_headers,
        ).status_code
        == 404
    )
    missing = {**request_for(first), "observation_ids": [str(uuid4())]}
    for request in (request_for(first), missing):
        assert (
            comparison_client.post(
                second_path + "/price-comparisons",
                headers=comparison_headers,
                json=request,
            ).status_code
            == 404
        )
    assert (
        comparison_client.get(
            second_path + "/price-comparisons", headers=comparison_headers
        ).json()["items"]
        == []
    )


def test_target_named_units_are_checked_against_owned_product(
    comparison_client,
    comparison_headers,
    product_path,
    observation_body,
):
    saved = save(comparison_client, comparison_headers, product_path, observation_body)
    request = request_for(saved)
    request["target_quantity"] = {"value": "1", "unit": "egg"}
    response = comparison_client.post(
        product_path + "/price-comparisons", headers=comparison_headers, json=request
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "target_quantity", "unit"]
    with Session(comparison_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(PriceComparison)) == 0


def test_pagination_for_observations_and_reports(
    comparison_client,
    comparison_headers,
    product_path,
    observation_body,
):
    records = [
        save(comparison_client, comparison_headers, product_path, observation_body)
        for _index in range(2)
    ]
    reports = [
        comparison_client.post(
            product_path + "/price-comparisons",
            headers=comparison_headers,
            json=request_for(records[0]),
        ).json()
        for _index in range(2)
    ]
    with Session(comparison_client.app.state.engine) as db, db.begin():
        for model in (PriceObservation, PriceComparison):
            for row in db.scalars(select(model)):
                row.created_at = datetime(2026, 1, 1)
    for suffix, saved in (("price-observations", records), ("price-comparisons", reports)):
        path = product_path + "/" + suffix
        for offset, expected in enumerate(sorted([row["id"] for row in saved], reverse=True)):
            response = comparison_client.get(
                path + f"?limit=1&offset={offset}", headers=comparison_headers
            )
            assert response.status_code == 200
            assert response.json()["items"][0]["id"] == expected
            assert response.json()["limit"] == 1 and response.json()["offset"] == offset
        assert (
            comparison_client.get(path + "?offset=2", headers=comparison_headers).json()["items"]
            == []
        )
        for query in ("?limit=0", "?limit=101", "?offset=-1"):
            assert (
                comparison_client.get(path + query, headers=comparison_headers).status_code == 422
            )
    summaries = comparison_client.get(
        product_path + "/price-comparisons", headers=comparison_headers
    ).json()["items"]
    assert "result" not in summaries[0]


@pytest.mark.parametrize("operation", ["observation", "report"])
def test_failed_storage_rolls_back(
    comparison_client,
    comparison_headers,
    product_path,
    observation_body,
    comparison_url,
    operation,
):
    saved = save(comparison_client, comparison_headers, product_path, observation_body)

    def fail_commit(_db):
        raise RuntimeError("Synthetic comparison storage failure")

    event.listen(Session, "before_commit", fail_commit)
    try:
        with TestClient(create_app(comparison_url), raise_server_exceptions=False) as failing:
            if operation == "observation":
                response = failing.post(
                    product_path + "/price-observations",
                    headers=comparison_headers,
                    json=observation_body,
                )
            else:
                response = failing.post(
                    product_path + "/price-comparisons",
                    headers=comparison_headers,
                    json=request_for(saved),
                )
            assert response.status_code == 500
    finally:
        event.remove(Session, "before_commit", fail_commit)
    with Session(comparison_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(PriceObservation)) == 1
        assert db.scalar(select(func.count()).select_from(PriceComparison)) == 0


def test_invalid_inputs_return_422_without_saving(
    comparison_client,
    comparison_headers,
    product_path,
    observation_body,
):
    response = comparison_client.post(
        product_path + "/price-observations",
        headers=comparison_headers,
        json={**observation_body, "observed_on": "2026-02-01"},
    )
    assert response.status_code == 422
    response = comparison_client.post(
        product_path + "/price-observations",
        headers=comparison_headers,
        json={**observation_body, "price": 8.0},
    )
    assert response.status_code == 422
    with Session(comparison_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(PriceObservation)) == 0


def test_egg_example_normalizes_to_eggs(comparison_client, comparison_headers):
    item = comparison_client.post(
        "/api/v1/products",
        headers=comparison_headers,
        json={
            "name": "Synthetic eggs",
            "product_type": "eggs",
            "selling_unit": "dozen eggs",
        },
    ).json()
    path = "/api/v1/products/" + item["id"]
    data = json.loads((BACKEND / "examples/comparisons/egg-observation.json").read_text())
    saved = save(comparison_client, comparison_headers, path, data)
    response = comparison_client.post(
        path + "/price-comparisons",
        headers=comparison_headers,
        json={
            "observation_ids": [saved["id"]],
            "target_quantity": {"value": "1", "unit": "egg"},
        },
    )
    assert response.status_code == 201
    assert response.json()["result"]["selected_price_range"]["minimum"] == "0.500000"


def test_migration_retains_prior_data(
    comparison_client,
    comparison_headers,
    product_path,
    observation_body,
    payload,
):
    assert (
        comparison_client.post(
            product_path + "/analyses",
            headers=comparison_headers,
            json=payload,
        ).status_code
        == 201
    )
    assert (
        comparison_client.put(
            product_path + "/quality-locks",
            headers=comparison_headers,
            json={
                "expected_revision": 0,
                "rules": [
                    {"key": "flag", "label": "Synthetic", "type": "boolean", "expected": True}
                ],
            },
        ).status_code
        == 200
    )
    assert (
        comparison_client.post(
            product_path + "/quality-evaluations",
            headers=comparison_headers,
            json={
                "candidate_label": "Synthetic",
                "expected_revision": 1,
                "claims": {"flag": {"type": "boolean", "value": True}},
            },
        ).status_code
        == 201
    )
    engine = comparison_client.app.state.engine
    previous_tables = (
        "accounts",
        "account_roles",
        "sessions",
        "products",
        "analyses",
        "seller_applications",
        "quality_lock_sets",
        "quality_evaluations",
    )

    def previous_rows():
        with engine.connect() as connection:
            return {
                table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
                for table in previous_tables
            }

    before = previous_rows()
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0003")
    command.upgrade(config, "head")
    command.check(config)
    assert previous_rows() == before
    saved = save(comparison_client, comparison_headers, product_path, observation_body)
    assert (
        comparison_client.post(
            product_path + "/price-comparisons",
            headers=comparison_headers,
            json=request_for(saved),
        ).status_code
        == 201
    )
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    command.downgrade(config, "0003")
    assert previous_rows() == before
    command.upgrade(config, "head")
    assert (
        comparison_client.get(
            product_path + "/price-observations", headers=comparison_headers
        ).json()["items"]
        == []
    )


def test_openapi_documents_numeric_strings_and_access(comparison_client):
    schema = comparison_client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        if "/price-observations" in path or "/price-comparisons" in path:
            for operation in methods.values():
                assert operation["security"] == [{"HTTPBearer": []}]
                assert {"401", "403", "404", "422"} <= set(operation["responses"])
    assert schema["components"]["schemas"]["Quantity"]["properties"]["value"]["type"] == "string"
    assert (
        schema["components"]["schemas"]["ObservationCreate"]["properties"]["price"]["type"]
        == "string"
    )
