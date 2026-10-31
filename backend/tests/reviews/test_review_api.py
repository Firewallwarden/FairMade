"""Private evidence selection, immutable review history, and failure paths."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import Analysis, PriceComparison, QualityEvaluation, SellerPricingReview

BACKEND = Path(__file__).parents[2]


def create(client, headers, selected, request=None):
    return client.post(
        selected["path"] + "/pricing-reviews",
        headers=headers,
        json=selected["request"] if request is None else request,
    )


def test_create_snapshot_read_and_restart(
    review_client,
    review_headers,
    selected_evidence,
    review_url,
    monkeypatch,
):
    selected = selected_evidence
    response = create(review_client, review_headers, selected)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["review_version"] == "seller-pricing-review-v1"
    assert saved["reviewed_on"] == "2026-01-31"
    assert saved["basis"] == "seller_reported_unverified"
    assert saved["request_snapshot"] == selected["request"]
    assert saved["evidence_snapshot"]["pricing_analysis"] == selected["analysis"]
    assert saved["evidence_snapshot"]["comparison_report"] == selected["comparison"]
    assert saved["evidence_snapshot"]["quality_evaluations"] == [selected["quality"]]
    assert saved["result"]["market_context"]["status"] == "comparable"
    assert (
        saved["result"]["market_context"]["reassessed_comparison"]["selected_price_range"][
            "minimum"
        ]
        == "8.000000"
    )
    assert (
        review_client.patch(
            selected["path"], headers=review_headers, json={"name": "Updated"}
        ).status_code
        == 200
    )
    assert (
        review_client.put(
            selected["path"] + "/quality-locks",
            headers=review_headers,
            json={
                "expected_revision": 1,
                "rules": [],
            },
        ).status_code
        == 200
    )

    def no_rebuild(*_args):
        raise AssertionError("Historical reads must not rebuild reviews")

    monkeypatch.setattr("fairmade.reviews.routes.build_review", no_rebuild)
    url = selected["path"] + "/pricing-reviews/" + saved["id"]
    assert review_client.get(url, headers=review_headers).json() == saved
    with TestClient(create_app(review_url)) as restarted:
        assert restarted.get(url, headers=review_headers).json() == saved
    for method in ("put", "patch", "delete"):
        assert (
            review_client.request(method, url, headers=review_headers, json={}).status_code == 405
        )


def test_review_reassesses_age_and_current_quality_revision(
    review_client,
    review_headers,
    selected_evidence,
    monkeypatch,
):
    selected = selected_evidence
    assert (
        review_client.put(
            selected["path"] + "/quality-locks",
            headers=review_headers,
            json={
                "expected_revision": 1,
                "rules": [],
            },
        ).status_code
        == 200
    )
    monkeypatch.setattr("fairmade.reviews.routes.utcnow", lambda: datetime(2026, 3, 3, tzinfo=UTC))
    response = create(review_client, review_headers, selected)
    assert response.status_code == 201
    result = response.json()["result"]
    assert result["market_context"]["status"] == "no_comparable_evidence"
    assert "QUALITY_EVALUATION_OUTDATED" in result["warnings"]
    assert result["quality"]["evaluations"][0]["applies_to_review_rules"] is False
    original = review_client.get(
        selected["path"] + "/price-comparisons/" + selected["comparison"]["id"],
        headers=review_headers,
    ).json()
    assert original == selected["comparison"]


def test_pricing_only_review_explicitly_reports_missing_evidence(
    review_client,
    review_headers,
    selected_evidence,
):
    response = create(
        review_client,
        review_headers,
        selected_evidence,
        {
            "pricing_analysis_id": selected_evidence["analysis"]["id"],
        },
    )
    assert response.status_code == 201
    result = response.json()["result"]
    assert result["market_context"]["status"] == result["quality"]["status"] == "not_provided"
    assert "QUALITY_EVIDENCE_MISSING" in result["warnings"]
    assert "COMPARISON_EVIDENCE_MISSING" in result["warnings"]


def test_no_mapping_is_not_silently_inferred_from_selling_unit(
    review_client,
    review_headers,
    selected_evidence,
):
    request = {**selected_evidence["request"], "production_unit_quantity": None}
    response = create(review_client, review_headers, selected_evidence, request)
    assert response.status_code == 201
    market = response.json()["result"]["market_context"]
    assert market["status"] == "basis_missing" and market["price_assessments"] == []


def test_failed_quality_is_not_outvoted_by_a_pass(
    review_client,
    review_headers,
    selected_evidence,
):
    selected = selected_evidence
    failed = review_client.post(
        selected["path"] + "/quality-evaluations",
        headers=review_headers,
        json={
            "candidate_label": "Synthetic failing candidate",
            "expected_revision": 1,
            "claims": {"flag": {"type": "boolean", "value": False}},
        },
    )
    assert failed.status_code == 201
    request = {
        **selected["request"],
        "quality_evaluation_ids": [
            selected["quality"]["id"],
            failed.json()["id"],
        ],
    }
    response = create(review_client, review_headers, selected, request)
    assert response.status_code == 201
    assert response.json()["result"]["quality"]["status"] == "needs_attention"
    assert "MANDATORY_QUALITY_REQUIREMENT_FAILED" in response.json()["result"]["warnings"]


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic invalid"])
def test_every_review_route_requires_authentication(
    review_client,
    selected_evidence,
    authorization,
):
    headers = {"Authorization": authorization} if authorization else {}
    path = selected_evidence["path"] + "/pricing-reviews"
    for method, suffix, body in [
        ("post", "", selected_evidence["request"]),
        ("get", "", None),
        ("get", "/" + str(uuid4()), None),
    ]:
        assert (
            review_client.request(method, path + suffix, headers=headers, json=body).status_code
            == 401
        )


@pytest.mark.parametrize("roles,pending", [((), False), ((), True), (("admin",), False)])
def test_buyers_pending_and_admin_only_cannot_read_cost_reviews(
    review_client,
    selected_evidence,
    account_factory,
    roles,
    pending,
):
    headers = account_factory("buyer@example.com", roles)
    if pending:
        assert (
            review_client.post("/api/v1/seller-applications", headers=headers, json={}).status_code
            == 201
        )
    path = selected_evidence["path"] + "/pricing-reviews"
    for method, suffix, body in [
        ("post", "", selected_evidence["request"]),
        ("get", "", None),
        ("get", "/" + str(uuid4()), None),
    ]:
        assert (
            review_client.request(method, path + suffix, headers=headers, json=body).status_code
            == 403
        )


@pytest.mark.parametrize(
    "field", ["pricing_analysis_id", "comparison_report_id", "quality_evaluation_ids"]
)
def test_missing_selected_evidence_is_not_partially_accepted(
    review_client,
    review_headers,
    selected_evidence,
    field,
):
    request = dict(selected_evidence["request"])
    request[field] = [str(uuid4())] if field.endswith("_ids") else str(uuid4())
    response = create(review_client, review_headers, selected_evidence, request)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"
    with Session(review_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(SellerPricingReview)) == 0


def test_cross_seller_and_cross_product_evidence_isolation(
    review_client,
    review_headers,
    selected_evidence,
    account_factory,
    payload,
):
    selected = selected_evidence
    first = create(review_client, review_headers, selected).json()
    other = account_factory("other@example.com", ("seller",))
    path = selected["path"] + "/pricing-reviews"
    assert create(review_client, other, selected).status_code == 404
    assert review_client.get(path, headers=other).status_code == 404
    assert review_client.get(path + "/" + first["id"], headers=other).status_code == 404
    second = review_client.post(
        "/api/v1/products",
        headers=review_headers,
        json={
            "name": "Another loaf",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    ).json()
    second_path = "/api/v1/products/" + second["id"]
    second_analysis = review_client.post(
        second_path + "/analyses", headers=review_headers, json=payload
    ).json()
    for request in (
        selected["request"],
        {**selected["request"], "pricing_analysis_id": second_analysis["id"]},
        {
            "pricing_analysis_id": second_analysis["id"],
            "quality_evaluation_ids": [selected["quality"]["id"]],
        },
    ):
        assert (
            review_client.post(
                second_path + "/pricing-reviews", headers=review_headers, json=request
            ).status_code
            == 404
        )
    assert (
        review_client.get(
            second_path + "/pricing-reviews/" + first["id"], headers=review_headers
        ).status_code
        == 404
    )


@pytest.mark.parametrize("kind", ["pricing", "pricing_result", "quality", "comparison"])
def test_unknown_evidence_versions_return_conflict(
    review_client,
    review_headers,
    selected_evidence,
    kind,
):
    selected = selected_evidence
    with Session(review_client.app.state.engine) as db, db.begin():
        if kind.startswith("pricing"):
            row = db.get(Analysis, selected["analysis"]["id"])
            if kind == "pricing":
                row.calculation_version = "future-version"
            else:
                row.result = {**row.result, "calculation_version": "future-version"}
        elif kind == "quality":
            db.get(
                QualityEvaluation, selected["quality"]["id"]
            ).evaluation_version = "future-version"
        else:
            db.get(
                PriceComparison, selected["comparison"]["id"]
            ).comparison_version = "future-version"
    response = create(review_client, review_headers, selected)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "UNSUPPORTED_EVIDENCE_VERSION"


def test_invalid_named_mapping_is_rejected(review_client, review_headers, selected_evidence):
    request = {
        **selected_evidence["request"],
        "production_unit_quantity": {"value": "1", "unit": "egg"},
    }
    response = create(review_client, review_headers, selected_evidence, request)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "production_unit_quantity", "unit"]


def test_pagination_uses_stable_order(review_client, review_headers, selected_evidence):
    saved = [create(review_client, review_headers, selected_evidence).json() for _index in range(2)]
    with Session(review_client.app.state.engine) as db, db.begin():
        for row in db.scalars(select(SellerPricingReview)):
            row.created_at = datetime(2026, 1, 1)
    path = selected_evidence["path"] + "/pricing-reviews"
    for offset, identifier in enumerate(sorted([item["id"] for item in saved], reverse=True)):
        response = review_client.get(path + f"?limit=1&offset={offset}", headers=review_headers)
        assert response.status_code == 200
        assert response.json()["items"][0]["id"] == identifier
        assert "result" not in response.json()["items"][0]
    for suffix in ("?limit=0", "?limit=101", "?offset=-1"):
        assert review_client.get(path + suffix, headers=review_headers).status_code == 422


def test_failed_commit_rolls_back_review(
    review_client, review_headers, selected_evidence, review_url
):
    def fail_commit(_db):
        raise RuntimeError("Synthetic review storage failure")

    event.listen(Session, "before_commit", fail_commit)
    try:
        with TestClient(create_app(review_url), raise_server_exceptions=False) as failing:
            assert create(failing, review_headers, selected_evidence).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail_commit)
    with Session(review_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(SellerPricingReview)) == 0
    assert create(review_client, review_headers, selected_evidence).status_code == 201


def test_migration_preserves_existing_evidence(review_client, review_headers, selected_evidence):
    engine = review_client.app.state.engine
    tables = (
        "accounts",
        "account_roles",
        "sessions",
        "products",
        "analyses",
        "quality_lock_sets",
        "quality_evaluations",
        "price_observations",
        "price_comparisons",
        "seller_applications",
    )

    def source_rows():
        with engine.connect() as connection:
            return {
                table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
                for table in tables
            }

    before = source_rows()
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0004")
    command.upgrade(config, "head")
    command.check(config)
    assert source_rows() == before
    assert create(review_client, review_headers, selected_evidence).status_code == 201
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    command.downgrade(config, "0004")
    assert source_rows() == before
    command.upgrade(config, "head")
    assert (
        review_client.get(
            selected_evidence["path"] + "/pricing-reviews", headers=review_headers
        ).json()["items"]
        == []
    )


def test_openapi_describes_private_review_contract(review_client):
    schema = review_client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        if "/pricing-reviews" in path:
            for operation in methods.values():
                assert operation["security"] == [{"HTTPBearer": []}]
                assert {"401", "403", "404", "422"} <= set(operation["responses"])
    assert (
        "409"
        in schema["paths"]["/api/v1/products/{product_id}/pricing-reviews"]["post"]["responses"]
    )
    assert schema["components"]["schemas"]["ReviewRequest"]["additionalProperties"] is False
