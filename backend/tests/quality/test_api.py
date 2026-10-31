"""Quality API behavior, access boundaries, persistence, and revision races."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import QualityEvaluation, QualityLockSet

BACKEND = Path(__file__).parents[2]


def install(client, headers, path, body):
    response = client.put(path + "/quality-locks", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def routes(path, lock_body, candidate_body):
    return [
        ("get", path + "/quality-locks", None),
        ("put", path + "/quality-locks", lock_body),
        ("post", path + "/quality-evaluations", candidate_body),
        ("get", path + "/quality-evaluations", None),
        ("get", path + "/quality-evaluations/" + str(uuid4()), None),
    ]


def test_get_is_side_effect_free_and_replacements_are_revisioned(
    quality_client,
    quality_headers,
    product_path,
    lock_body,
):
    path = product_path + "/quality-locks"
    assert quality_client.get(path, headers=quality_headers).json() == {"revision": 0, "rules": []}
    with Session(quality_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(QualityLockSet)) == 0
    installed = install(quality_client, quality_headers, product_path, lock_body)
    assert installed["revision"] == 1
    assert installed["rules"][2]["minimum"] == "24"
    assert quality_client.get(path, headers=quality_headers).json() == installed
    response = quality_client.put(path, headers=quality_headers, json=lock_body)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REVISION_CONFLICT"
    cleared = install(
        quality_client,
        quality_headers,
        product_path,
        {
            "expected_revision": 1,
            "rules": [],
        },
    )
    assert cleared == {"revision": 2, "rules": []}
    assert quality_client.put(path, headers=quality_headers, json=lock_body).status_code == 409


def test_save_and_read_history_survives_rules_edits_and_restart(
    quality_client,
    quality_headers,
    product_path,
    lock_body,
    candidate_body,
    quality_url,
    monkeypatch,
):
    installed = install(quality_client, quality_headers, product_path, lock_body)
    path = product_path + "/quality-evaluations"
    response = quality_client.post(path, headers=quality_headers, json=candidate_body)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["status"] == "passed"
    assert saved["basis"] == "seller_reported_unverified"
    assert saved["evaluation_version"] == "quality-evaluation-v1"
    assert saved["rules_snapshot"] == installed["rules"]
    assert saved["claims"] == candidate_body["claims"]
    assert saved["rule_revision"] == 1
    assert saved["created_at"].endswith("Z")
    install(quality_client, quality_headers, product_path, {"expected_revision": 1, "rules": []})
    assert (
        quality_client.post(
            path,
            headers=quality_headers,
            json=candidate_body,
        ).status_code
        == 409
    )

    # Rule clearing and calculator code changes cannot reinterpret old results.
    def cannot_recalculate(*_args):
        raise AssertionError("Historical reads must not recalculate")

    monkeypatch.setattr("fairmade.quality.routes.evaluate", cannot_recalculate)
    detail = path + "/" + saved["id"]
    assert quality_client.get(detail, headers=quality_headers).json() == saved
    with TestClient(create_app(quality_url)) as restarted:
        assert restarted.get(detail, headers=quality_headers).json() == saved
    history = quality_client.get(path, headers=quality_headers).json()
    assert history["limit"] == 20 and history["offset"] == 0
    assert len(history["items"]) == 1
    assert history["items"][0]["id"] == saved["id"]
    assert "claims" not in history["items"][0]
    for method in ("put", "patch", "delete"):
        assert (
            quality_client.request(method, detail, headers=quality_headers, json={}).status_code
            == 405
        )


def test_unconfigured_rules_do_not_implicitly_pass(quality_client, quality_headers, product_path):
    response = quality_client.post(
        product_path + "/quality-evaluations",
        headers=quality_headers,
        json={
            "expected_revision": 0,
            "candidate_label": "Synthetic",
            "claims": {},
        },
    )
    assert response.status_code == 201
    saved = response.json()
    assert saved["status"] == "not_evaluated"
    assert saved["rules_snapshot"] == saved["checks"] == []
    assert saved["rule_revision"] == 0


def test_unknown_and_stale_claims_do_not_create_history(
    quality_client,
    quality_headers,
    product_path,
    lock_body,
    candidate_body,
):
    path = product_path + "/quality-evaluations"
    # A stale request must not initialize a persistent rule set.
    assert (
        quality_client.post(path, headers=quality_headers, json=candidate_body).status_code == 409
    )
    with Session(quality_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(QualityLockSet)) == 0
    install(quality_client, quality_headers, product_path, lock_body)
    candidate_body["claims"]["typo"] = {"type": "boolean", "value": True}
    response = quality_client.post(path, headers=quality_headers, json=candidate_body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "claims", "typo"]
    assert quality_client.get(path, headers=quality_headers).json()["items"] == []


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic invalid"])
def test_all_quality_routes_require_authentication(
    quality_client,
    product_path,
    lock_body,
    candidate_body,
    authorization,
):
    headers = {"Authorization": authorization} if authorization else {}
    for method, path, body in routes(product_path, lock_body, candidate_body):
        assert quality_client.request(method, path, headers=headers, json=body).status_code == 401


@pytest.mark.parametrize("roles,pending", [((), False), ((), True), (("admin",), False)])
def test_buyers_pending_and_admin_accounts_cannot_access_quality_data(
    quality_client,
    product_path,
    account_factory,
    lock_body,
    candidate_body,
    roles,
    pending,
):
    headers = account_factory("buyer@example.com", roles)
    if pending:
        assert (
            quality_client.post(
                "/api/v1/seller-applications",
                headers=headers,
                json={},
            ).status_code
            == 201
        )
    for method, path, body in routes(product_path, lock_body, candidate_body):
        response = quality_client.request(method, path, headers=headers, json=body)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "SELLER_REQUIRED"


def test_seller_ownership_and_parent_matching(
    quality_client,
    quality_headers,
    product_path,
    account_factory,
    lock_body,
    candidate_body,
):
    install(quality_client, quality_headers, product_path, lock_body)
    saved = quality_client.post(
        product_path + "/quality-evaluations",
        headers=quality_headers,
        json=candidate_body,
    ).json()
    other = account_factory("other@example.com", ("seller",))
    for method, path, body in routes(product_path, lock_body, candidate_body):
        assert quality_client.request(method, path, headers=other, json=body).status_code == 404
    detail = product_path + "/quality-evaluations/" + saved["id"]
    assert quality_client.get(detail, headers=other).status_code == 404
    second = quality_client.post(
        "/api/v1/products",
        headers=quality_headers,
        json={
            "name": "Other loaf",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    ).json()
    mismatched = f"/api/v1/products/{second['id']}/quality-evaluations/{saved['id']}"
    assert quality_client.get(mismatched, headers=quality_headers).status_code == 404
    for method, path, body in routes("/api/v1/products/" + str(uuid4()), lock_body, candidate_body):
        assert (
            quality_client.request(method, path, headers=quality_headers, json=body).status_code
            == 404
        )


def test_pagination_and_validation(
    quality_client, quality_headers, product_path, lock_body, candidate_body
):
    install(quality_client, quality_headers, product_path, lock_body)
    path = product_path + "/quality-evaluations"
    saved = [
        quality_client.post(path, headers=quality_headers, json=candidate_body).json()
        for _index in range(2)
    ]
    with Session(quality_client.app.state.engine) as db, db.begin():
        for item in db.scalars(select(QualityEvaluation)):
            item.created_at = datetime(2026, 1, 1)
    for offset, expected in enumerate(sorted([item["id"] for item in saved], reverse=True)):
        response = quality_client.get(path + f"?limit=1&offset={offset}", headers=quality_headers)
        assert response.status_code == 200
        assert response.json()["items"][0]["id"] == expected
        assert response.json()["limit"] == 1 and response.json()["offset"] == offset
    assert quality_client.get(path + "?offset=2", headers=quality_headers).json()["items"] == []
    for query in ("?limit=0", "?limit=101", "?offset=-1"):
        assert quality_client.get(path + query, headers=quality_headers).status_code == 422
    candidate_body["claims"]["organic_flour"]["value"] = "true"
    assert (
        quality_client.post(path, headers=quality_headers, json=candidate_body).status_code == 422
    )
    lock_body["rules"][0]["mandatory"] = False
    assert (
        quality_client.put(
            product_path + "/quality-locks",
            headers=quality_headers,
            json=lock_body,
        ).status_code
        == 422
    )


@pytest.mark.parametrize("initial_revision", [0, 1])
def test_concurrent_replacements_have_one_winner(
    quality_client,
    quality_headers,
    quality_url,
    product_path,
    lock_body,
    initial_revision,
):
    if initial_revision:
        install(quality_client, quality_headers, product_path, lock_body)
    barrier = Barrier(2)

    def replace(index):
        with TestClient(create_app(quality_url)) as client:
            barrier.wait(timeout=10)
            body = {
                "expected_revision": initial_revision,
                "rules": [
                    {
                        "key": "flag",
                        "label": f"Writer {index}",
                        "type": "boolean",
                        "expected": True,
                    }
                ],
            }
            return client.put(product_path + "/quality-locks", headers=quality_headers, json=body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(replace, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert winner["revision"] == initial_revision + 1
    assert (
        quality_client.get(product_path + "/quality-locks", headers=quality_headers).json()
        == winner
    )


def test_evaluation_racing_replacement_never_uses_the_wrong_snapshot(
    quality_client,
    quality_headers,
    quality_url,
    product_path,
    lock_body,
    candidate_body,
):
    installed = install(quality_client, quality_headers, product_path, lock_body)
    barrier = Barrier(2)

    def race(action):
        with TestClient(create_app(quality_url)) as client:
            barrier.wait(timeout=10)
            if action == "evaluate":
                return client.post(
                    product_path + "/quality-evaluations",
                    headers=quality_headers,
                    json=candidate_body,
                )
            return client.put(
                product_path + "/quality-locks",
                headers=quality_headers,
                json={
                    "expected_revision": 1,
                    "rules": [],
                },
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        checked, replaced = list(executor.map(race, ["evaluate", "replace"]))
    assert replaced.status_code == 200
    assert checked.status_code in (201, 409)
    history = quality_client.get(
        product_path + "/quality-evaluations", headers=quality_headers
    ).json()
    assert len(history["items"]) == (1 if checked.status_code == 201 else 0)
    if checked.status_code == 201:
        assert checked.json()["rules_snapshot"] == installed["rules"]
        assert checked.json()["rule_revision"] == 1 and checked.json()["status"] == "passed"


@pytest.mark.parametrize("operation", ["replace", "evaluate"])
def test_failed_commits_rollback_all_quality_writes(
    quality_client,
    quality_headers,
    quality_url,
    product_path,
    lock_body,
    operation,
):
    def fail_commit(_db):
        raise RuntimeError("Simulated quality storage failure")

    event.listen(Session, "before_commit", fail_commit)
    try:
        with TestClient(create_app(quality_url), raise_server_exceptions=False) as failing:
            if operation == "replace":
                response = failing.put(
                    product_path + "/quality-locks", headers=quality_headers, json=lock_body
                )
            else:
                response = failing.post(
                    product_path + "/quality-evaluations",
                    headers=quality_headers,
                    json={
                        "expected_revision": 0,
                        "candidate_label": "Demo",
                        "claims": {},
                    },
                )
            assert response.status_code == 500
    finally:
        event.remove(Session, "before_commit", fail_commit)
    assert quality_client.get(product_path + "/quality-locks", headers=quality_headers).json() == {
        "revision": 0,
        "rules": [],
    }
    with Session(quality_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(QualityLockSet)) == 0
        assert db.scalar(select(func.count()).select_from(QualityEvaluation)) == 0


def test_egg_example_excludes_failed_welfare_claim(quality_client, quality_headers):
    product = quality_client.post(
        "/api/v1/products",
        headers=quality_headers,
        json={
            "name": "Synthetic eggs",
            "product_type": "eggs",
            "selling_unit": "dozen eggs",
        },
    ).json()
    path = "/api/v1/products/" + product["id"]
    locks = json.loads((BACKEND / "examples/quality/egg-locks.json").read_text())
    candidate = json.loads((BACKEND / "examples/quality/egg-candidate.json").read_text())
    install(quality_client, quality_headers, path, locks)
    response = quality_client.post(
        path + "/quality-evaluations", headers=quality_headers, json=candidate
    )
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["checks"][0]["reason_code"] == "BOOLEAN_MISMATCH"
    assert response.json()["basis"] == "seller_reported_unverified"


def test_quality_migration_preserves_prior_data(
    quality_client,
    quality_headers,
    quality_url,
    product_path,
    lock_body,
    candidate_body,
    payload,
):
    # Existing identity, role, product, session, application and pricing rows remain byte-for-byte.
    assert (
        quality_client.post(
            product_path + "/analyses",
            headers=quality_headers,
            json=payload,
        ).status_code
        == 201
    )
    old_tables = (
        "accounts",
        "account_roles",
        "sessions",
        "products",
        "analyses",
        "seller_applications",
    )
    engine = quality_client.app.state.engine

    def old_rows():
        with engine.connect() as connection:
            return {
                table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
                for table in old_tables
            }

    before = old_rows()
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0002")
    assert old_rows() == before
    command.upgrade(config, "head")
    command.check(config)
    assert old_rows() == before
    assert quality_client.get(product_path + "/quality-locks", headers=quality_headers).json() == {
        "revision": 0,
        "rules": [],
    }
    install(quality_client, quality_headers, product_path, lock_body)
    assert (
        quality_client.post(
            product_path + "/quality-evaluations",
            headers=quality_headers,
            json=candidate_body,
        ).status_code
        == 201
    )
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    command.downgrade(config, "0002")
    assert old_rows() == before
    command.upgrade(config, "head")
    assert (
        quality_client.get(product_path + "/quality-evaluations", headers=quality_headers).json()[
            "items"
        ]
        == []
    )


def test_quality_openapi_and_put_preflight(quality_client, quality_url, monkeypatch):
    schema = quality_client.get("/openapi.json").json()
    for path, operations in schema["paths"].items():
        if "/quality-" in path:
            for operation in operations.values():
                assert operation["security"] == [{"HTTPBearer": []}]
                assert {"401", "403", "404"} <= set(operation["responses"])
    numeric = schema["components"]["schemas"]["NumericClaim"]["properties"]["value"]
    assert numeric["type"] == "string"
    monkeypatch.setenv("FAIRMADE_CORS_ORIGINS", "http://localhost:5173")
    with TestClient(create_app(quality_url)) as client:
        response = client.options(
            "/api/v1/products/placeholder/quality-locks",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        response = client.options(
            "/api/v1/products/placeholder/quality-locks",
            headers={
                "Origin": "http://unapproved.example",
                "Access-Control-Request-Method": "PUT",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
