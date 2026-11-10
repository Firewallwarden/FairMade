"""Private identity, exact reported metrics, corrections and authorization."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import SupplierExperience, SupplierProfile, SupplierProfileEvent

BASE = "/api/v1/seller/suppliers"


def replacement(profile, **changes):
    return {
        "request_id": str(uuid4()),
        "expected_revision": profile["revision"],
        "name": profile["name"],
        "location": profile["location"],
        "notes": profile["notes"],
        "archived": profile["archived"],
        "reason": "Synthetic profile correction",
        **changes,
    }


def test_profile_history_exact_retries_archive_and_per_seller_names(
    market_client,
    record_headers,
    record_actor_factory,
    profile_body,
):
    original = market_client.post(BASE, headers=record_headers, json=profile_body)
    assert original.status_code == 201
    data = original.json()
    profile = data["after"]
    path = BASE + "/" + profile["id"]
    assert data["before"] is None and data["revision"] == 1
    assert original.headers["Cache-Control"] == "no-store" and data["created_at"].endswith("Z")
    assert "account_id" not in original.text and "name_key" not in original.text
    update_body = replacement(profile, name="Renamed supplier", archived=True)
    update = market_client.put(path, headers=record_headers, json=update_body)
    assert update.status_code == 200, update.text
    assert update.json()["before"] == profile
    assert market_client.post(BASE, headers=record_headers, json=profile_body).json() == data
    assert market_client.put(path, headers=record_headers, json=update_body).json() == update.json()
    assert market_client.get(path, headers=record_headers).json()["archived"] is True
    assert market_client.get(BASE + "?archived=false", headers=record_headers).json()["items"] == []
    history = market_client.get(path + "/history?limit=1&offset=1", headers=record_headers).json()
    assert history["items"] == [data]
    stale = market_client.put(path, headers=record_headers, json=replacement(profile))
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "REVISION_CONFLICT"
    conflict = market_client.put(
        path, headers=record_headers, json={**update_body, "name": "Different"}
    )
    assert (
        conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    )
    collision = {**profile_body, "request_id": str(uuid4()), "name": "  renamed SUPPLIER  "}
    assert market_client.post(BASE, headers=record_headers, json=collision).status_code == 409
    # The same supplier name belongs to a separate private record for another seller.
    other = record_actor_factory()
    assert market_client.post(BASE, headers=other, json=collision).status_code == 201
    assert len(market_client.get(BASE, headers=other).json()["items"]) == 1


def test_unknown_metrics_and_exact_corrected_delivery_denominators(
    market_client,
    record_headers,
    supplier_profile,
    experience_body,
):
    path = BASE + "/" + supplier_profile["id"]
    empty = market_client.get(path + "/reliability", headers=record_headers).json()
    assert empty["experiences_count"] == 0
    assert empty["average_rating"] is None and empty["on_time_fraction"] is None
    reports = []
    changes = [
        {},
        {"rating": 2, "received_on": "2025-05-08"},
        {"rating": None, "promised_on": None},
        {"rating": None, "received_on": None},
        {"rating": None, "promised_on": None, "received_on": None},
    ]
    for change in changes:
        response = market_client.post(
            path + "/experiences",
            headers=record_headers,
            json={
                **experience_body,
                "request_id": str(uuid4()),
                **change,
            },
        )
        assert response.status_code == 201, response.text
        reports.append(response.json())
    summary = market_client.get(path + "/reliability", headers=record_headers).json()
    assert summary["experiences_count"] == 5 and summary["rated_count"] == 2
    assert summary["average_rating"] == "3.000000"
    assert summary["dated_deliveries_count"] == 2 and summary["on_time_count"] == 1
    assert summary["late_count"] == 1 and summary["unknown_delivery_count"] == 3
    assert summary["on_time_fraction"] == "0.500000"
    assert "not verified" in summary["notices"][0]
    assert "Quality Locks" in summary["notices"][2]
    replacement_body = {
        **reports[1]["request"],
        "request_id": str(uuid4()),
        "rating": 5,
        "received_on": "2025-05-07",
        "corrects_experience_id": reports[1]["id"],
        "correction_reason": "Synthetic corrected receipt date",
    }
    corrected = market_client.post(
        path + "/experiences", headers=record_headers, json=replacement_body
    )
    assert corrected.status_code == 201
    summary = market_client.get(path + "/reliability", headers=record_headers).json()
    assert summary["experiences_count"] == 5 and summary["average_rating"] == "4.500000"
    assert summary["on_time_fraction"] == "1.000000" and summary["late_count"] == 0
    older = market_client.get(
        path + "/experiences/" + reports[1]["id"], headers=record_headers
    ).json()
    assert older == reports[1]
    default = market_client.get(path + "/experiences", headers=record_headers).json()["items"]
    assert len(default) == 5 and reports[1]["id"] not in {row["id"] for row in default}
    full = market_client.get(
        path + "/experiences?include_corrected=true", headers=record_headers
    ).json()["items"]
    assert len(full) == 6
    assert "request" not in full[0] and "supplier_snapshot" not in full[0]
    blocked = market_client.post(
        path + "/experiences",
        headers=record_headers,
        json={
            **replacement_body,
            "request_id": str(uuid4()),
        },
    )
    assert (
        blocked.status_code == 409
        and blocked.json()["detail"]["code"] == "EXPERIENCE_ALREADY_CORRECTED"
    )


def test_profile_and_quote_snapshots_stay_frozen_after_rename_and_archive(
    market_client,
    record_headers,
    supplier_profile,
    experience_body,
    owned_quote_factory,
):
    quote_path, quote = owned_quote_factory()
    path = BASE + "/" + supplier_profile["id"]
    body = {**experience_body, "source_quote_id": quote["id"]}
    first = market_client.post(path + "/experiences", headers=record_headers, json=body).json()
    assert first["supplier_snapshot"] == supplier_profile and first["quote_snapshot"] == quote
    update = market_client.put(
        path,
        headers=record_headers,
        json=replacement(supplier_profile, name="New name", archived=True),
    ).json()
    assert (
        market_client.post(path + "/experiences", headers=record_headers, json=body).json() == first
    )
    conflicting = market_client.post(
        path + "/experiences", headers=record_headers, json={**body, "rating": 1}
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    stale = market_client.post(
        path + "/experiences", headers=record_headers, json={**body, "request_id": str(uuid4())}
    )
    assert stale.status_code == 409
    correction = {
        **body,
        "request_id": str(uuid4()),
        "corrects_experience_id": first["id"],
        "correction_reason": "Correcting opinion only",
        "rating": 3,
    }
    fixed = market_client.post(path + "/experiences", headers=record_headers, json=correction)
    assert fixed.status_code == 201, fixed.text
    assert fixed.json()["supplier_snapshot"] == first["supplier_snapshot"]
    assert fixed.json()["quote_snapshot"] == quote
    assert (
        market_client.get(
            quote_path + "/supplier-quotes/" + quote["id"], headers=record_headers
        ).json()
        == quote
    )
    # Archival still allows reporting past experiences with a selected current revision.
    current = update["after"]
    assert (
        market_client.post(
            path + "/experiences",
            headers=record_headers,
            json={
                **body,
                "request_id": str(uuid4()),
                "expected_supplier_revision": current["revision"],
            },
        ).status_code
        == 201
    )


def test_date_filters_and_correction_moved_outside_window(
    market_client,
    record_headers,
    supplier_profile,
    experience_body,
):
    path = BASE + "/" + supplier_profile["id"]
    original = market_client.post(
        path + "/experiences", headers=record_headers, json=experience_body
    ).json()
    correction = {
        **experience_body,
        "request_id": str(uuid4()),
        "observed_on": "2025-06-01",
        "corrects_experience_id": original["id"],
        "correction_reason": "Correcting observation date",
    }
    assert (
        market_client.post(
            path + "/experiences", headers=record_headers, json=correction
        ).status_code
        == 201
    )
    window = "?observed_from=2025-05-01&observed_until=2025-05-31"
    assert (
        market_client.get(path + "/experiences" + window, headers=record_headers).json()["items"]
        == []
    )
    summary = market_client.get(path + "/reliability" + window, headers=record_headers).json()
    assert summary["experiences_count"] == 0 and summary["on_time_fraction"] is None
    assert (
        len(
            market_client.get(
                path + "/experiences" + window + "&include_corrected=true", headers=record_headers
            ).json()["items"]
        )
        == 1
    )
    response = market_client.get(
        path + "/reliability?observed_from=2025-06-01&observed_until=2025-05-01",
        headers=record_headers,
    )
    assert response.status_code == 422 and response.json()["detail"]["code"] == "INVALID_DATE_RANGE"


def test_all_routes_roles_ownership_and_unshared_aggregate(
    market_client,
    record_headers,
    record_actor_factory,
    supplier_profile,
    experience_body,
):
    path = BASE + "/" + supplier_profile["id"]
    record = market_client.post(
        path + "/experiences", headers=record_headers, json=experience_body
    ).json()
    actors = [
        ({}, 401),
        (record_actor_factory(("buyer",)), 403),
        (record_actor_factory(("buyer", "admin")), 403),
        (record_actor_factory(), 404),
    ]
    routes = [
        ("get", path, None),
        ("put", path, replacement(supplier_profile)),
        ("get", path + "/history", None),
        ("get", path + "/reliability", None),
        ("get", path + "/experiences", None),
        ("get", path + "/experiences/" + record["id"], None),
        ("post", path + "/experiences", experience_body),
    ]
    for headers, status in actors:
        for method, url, body in routes:
            kwargs = {"json": body} if body else {}
            response = market_client.request(method, url, headers=headers, **kwargs)
            assert response.status_code == status
            assert response.headers["Cache-Control"] == "no-store"
            assert "PRIVATE_BUSINESS_NOTES" not in response.text
            if status == 401:
                assert response.headers["WWW-Authenticate"] == "Bearer"
    assert market_client.get(BASE, headers=actors[-1][0]).json()["items"] == []
    for headers, status in actors[:-1]:
        assert market_client.get(BASE, headers=headers).status_code == status
        assert (
            market_client.post(
                BASE, headers=headers, json={"request_id": str(uuid4()), "name": "Demo"}
            ).status_code
            == status
        )


def test_quote_and_correction_references_cannot_cross_owners_or_suppliers(
    market_client,
    record_headers,
    record_actor_factory,
    supplier_profile,
    experience_body,
    owned_quote_factory,
):
    other = record_actor_factory()
    _, private_quote = owned_quote_factory(other)
    path = BASE + "/" + supplier_profile["id"]
    response = market_client.post(
        path + "/experiences",
        headers=record_headers,
        json={
            **experience_body,
            "source_quote_id": private_quote["id"],
        },
    )
    assert response.status_code == 404
    assert (
        market_client.get(path + "/reliability", headers=record_headers).json()["experiences_count"]
        == 0
    )
    first = market_client.post(
        path + "/experiences", headers=record_headers, json=experience_body
    ).json()
    another = market_client.post(
        BASE, headers=record_headers, json={"request_id": str(uuid4()), "name": "Another"}
    ).json()["after"]
    correction = {
        **experience_body,
        "request_id": str(uuid4()),
        "corrects_experience_id": first["id"],
        "correction_reason": "Wrong supplier",
    }
    assert (
        market_client.post(
            BASE + "/" + another["id"] + "/experiences", headers=record_headers, json=correction
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"rating": True},
        {"rating": 0},
        {"rating": 6},
        {"rating": "5"},
        {"observed_on": "2999-01-01"},
        {"received_on": "2025-05-09"},
        {"label": " "},
        {"notes": "x" * 2001},
        {"account_id": "PRIVATE_OWNER_INJECTION"},
        {"source_quote_id": "PRIVATE_BAD_UUID"},
        {"correction_reason": "No prior"},
        {"corrects_experience_id": "24000000-0000-4000-8000-000000000099"},
    ],
)
def test_invalid_experience_inputs_are_redacted(
    market_client, record_headers, supplier_profile, experience_body, changes
):
    response = market_client.post(
        BASE + "/" + supplier_profile["id"] + "/experiences",
        headers=record_headers,
        json={**experience_body, **changes},
    )
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert (
        "PRIVATE_OWNER_INJECTION" not in response.text and "PRIVATE_BAD_UUID" not in response.text
    )
    assert all("input" not in value for value in response.json()["detail"])
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(SupplierExperience)) == 0


def test_profile_invalid_metadata_and_informative_observation_required(
    market_client,
    record_headers,
    supplier_profile,
    experience_body,
):
    for body in (
        {"name": " "},
        {"name": "Demo", "archived": 1},
        {"name": "Demo", "owner_id": "PRIVATE_OWNER"},
    ):
        response = market_client.post(
            BASE, headers=record_headers, json={"request_id": str(uuid4()), **body}
        )
        assert response.status_code == 422
        assert "PRIVATE_OWNER" not in response.text
    path = BASE + "/" + supplier_profile["id"]
    empty = {
        **experience_body,
        "rating": None,
        "promised_on": None,
        "received_on": None,
        "notes": " ",
    }
    assert (
        market_client.post(path + "/experiences", headers=record_headers, json=empty).status_code
        == 422
    )
    invalid = replacement(supplier_profile, reason="\x00")
    assert market_client.put(path, headers=record_headers, json=invalid).status_code == 422


def test_concurrent_profile_and_experience_retries_and_corrections(
    market_client,
    record_headers,
    profile_body,
    experience_body,
):
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda _: market_client.post(BASE, headers=record_headers, json=profile_body),
                range(2),
            )
        )
    assert sorted(response.status_code for response in replies) == [200, 201]
    assert replies[0].json() == replies[1].json()
    path = BASE + "/" + replies[0].json()["after"]["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda _: market_client.post(
                    path + "/experiences", headers=record_headers, json=experience_body
                ),
                range(2),
            )
        )
    assert sorted(response.status_code for response in replies) == [200, 201]
    assert replies[0].json() == replies[1].json()
    original = replies[0].json()

    def correction(rating):
        return {
            **experience_body,
            "request_id": str(uuid4()),
            "rating": rating,
            "corrects_experience_id": original["id"],
            "correction_reason": "Synthetic correction",
        }

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda body: market_client.post(
                    path + "/experiences", headers=record_headers, json=body
                ),
                [correction(2), correction(5)],
            )
        )
    assert sorted(response.status_code for response in replies) == [201, 409]


@pytest.mark.parametrize("kind", ["profile", "experience"])
def test_commit_failure_is_atomic_and_retry_key_remains_usable(
    market_client,
    record_headers,
    supplier_profile,
    profile_body,
    experience_body,
    market_url,
    kind,
):
    path = BASE if kind == "profile" else BASE + "/" + supplier_profile["id"] + "/experiences"
    body = (
        {**profile_body, "request_id": str(uuid4()), "name": "Failed new profile"}
        if kind == "profile"
        else experience_body
    )
    record_type = SupplierProfileEvent if kind == "profile" else SupplierExperience

    def fail(db):
        if any(isinstance(row, record_type) for row in db.new):
            raise RuntimeError("Synthetic supplier-record commit failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert client.post(path, headers=record_headers, json=body).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(SupplierProfile)) == 1
        assert db.scalar(select(func.count()).select_from(SupplierExperience)) == 0
    assert market_client.post(path, headers=record_headers, json=body).status_code == 201


def test_no_public_routes_pagination_and_exact_summary_query(
    market_client, record_headers, supplier_profile, experience_body
):
    path = BASE + "/" + supplier_profile["id"]
    first = market_client.post(
        path + "/experiences", headers=record_headers, json=experience_body
    ).json()
    market_client.post(
        path + "/experiences",
        headers=record_headers,
        json={**experience_body, "request_id": str(uuid4())},
    )
    page = market_client.get(path + "/experiences?limit=1&offset=1", headers=record_headers).json()
    assert [row["id"] for row in page["items"]] == [first["id"]]
    schema = market_client.get("/openapi.json").json()
    for url, methods in schema["paths"].items():
        if url.startswith(BASE):
            assert all(method["security"] == [{"HTTPBearer": []}] for method in methods.values())
    for query in ("limit=101", "offset=-1", "archived=invalid"):
        assert market_client.get(BASE + "?" + query, headers=record_headers).status_code == 422
    queries = []

    def capture(_connection, _cursor, statement, _params, _context, _many):
        if "FROM supplier_experiences" in statement:
            queries.append(statement)

    engine = market_client.app.state.engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        summary = market_client.get(path + "/reliability", headers=record_headers)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert summary.status_code == 200 and len(queries) == 1
    assert "supplier_snapshot" not in queries[0] and " AVG(" not in queries[0]


def test_recurring_averages_and_missing_rating_denominators(
    market_client,
    record_headers,
    supplier_profile,
    experience_body,
):
    path = BASE + "/" + supplier_profile["id"]
    for rating in (5, 5, 4, None):
        response = market_client.post(
            path + "/experiences",
            headers=record_headers,
            json={
                **experience_body,
                "request_id": str(uuid4()),
                "rating": rating,
                "received_on": "2025-05-06" if rating == 4 else "2025-05-08",
                "promised_on": "2025-05-07" if rating is not None else None,
            },
        )
        assert response.status_code == 201
    summary = market_client.get(path + "/reliability", headers=record_headers).json()
    assert summary["rated_count"] == 3 and summary["average_rating"] == "4.666667"
    assert summary["dated_deliveries_count"] == 3 and summary["on_time_fraction"] == "0.333333"
    assert summary["unknown_delivery_count"] == 1


def test_competing_profile_replacements_keep_one_current_revision(
    market_client,
    record_headers,
    supplier_profile,
):
    path = BASE + "/" + supplier_profile["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda body: market_client.put(path, headers=record_headers, json=body),
                [
                    replacement(supplier_profile, notes="First"),
                    replacement(supplier_profile, notes="Second"),
                ],
            )
        )
    assert sorted(reply.status_code for reply in replies) == [200, 409]
    assert market_client.get(path, headers=record_headers).json()["revision"] == 2
    assert len(market_client.get(path + "/history", headers=record_headers).json()["items"]) == 2
