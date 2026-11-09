"""Frozen production sources, corrections and owner-scoped source histories."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import Analysis, MaterialMovement, ProductionLivestockSource, ProductionRecord

from .test_livestock_api import BASE, replace_body


def source(kind, profile):
    return {"kind": kind, "id": profile["id"], "expected_revision": profile["revision"]}


def test_both_source_types_snapshots_and_no_side_effects(
    market_client,
    market_headers,
    livestock_group,
    livestock_animal,
    livestock_product,
    livestock_production_body,
):
    path = livestock_product + "/production-records"
    records = []
    for kind, profile in (("group", livestock_group), ("animal", livestock_animal)):
        request = {
            **livestock_production_body,
            "request_id": str(uuid4()),
            "livestock_source": source(kind, profile),
        }
        response = market_client.post(path, headers=market_headers, json=request)
        assert response.status_code == 201, response.text
        record = response.json()
        records.append(record)
        snapshot = record["livestock_snapshot"]
        assert snapshot["kind"] == kind
        assert snapshot["group"] == livestock_group
        assert snapshot["animal"] == (livestock_animal if kind == "animal" else None)
        assert snapshot["basis"] == "seller_reported_unverified"
        assert "not proof" in snapshot["notice"]
        assert record["result"]["unit_cost"] == "4.285714"
        assert "account_id" not in response.text
        assert market_client.post(path, headers=market_headers, json=request).json() == record
    # Registering and producing do not assert quality, update stock, or create pricing analyses.
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Analysis)) == 0
        assert db.scalar(select(func.count()).select_from(MaterialMovement)) == 0
    group_path = BASE + "/groups/" + livestock_group["id"]
    animal_path = BASE + "/animals/" + livestock_animal["id"]
    assert (
        market_client.put(
            group_path,
            headers=market_headers,
            json=replace_body(
                livestock_group,
                name="Renamed flock",
                reported_headcount=35,
            ),
        ).status_code
        == 200
    )
    assert (
        market_client.put(
            animal_path,
            headers=market_headers,
            json=replace_body(
                livestock_animal,
                identifier="New identifier",
                group_id=None,
            ),
        ).status_code
        == 200
    )
    for record in records:
        assert market_client.get(path + "/" + record["id"], headers=market_headers).json() == record
    # Group view includes direct group records and individuals attributed to that group then.
    group_records = market_client.get(
        group_path + "/production-records", headers=market_headers
    ).json()
    assert {record["id"] for record in group_records["items"]} == {r["id"] for r in records}
    animal_records = market_client.get(
        animal_path + "/production-records", headers=market_headers
    ).json()
    assert [record["id"] for record in animal_records["items"]] == [records[1]["id"]]


def test_corrections_keep_or_explicitly_replace_source(
    market_client,
    market_headers,
    livestock_group,
    livestock_animal,
    livestock_product,
    livestock_production_body,
):
    path = livestock_product + "/production-records"
    body = {**livestock_production_body, "livestock_source": source("animal", livestock_animal)}
    original = market_client.post(path, headers=market_headers, json=body).json()
    animal_path = BASE + "/animals/" + livestock_animal["id"]
    market_client.put(
        animal_path,
        headers=market_headers,
        json=replace_body(
            livestock_animal,
            group_id=None,
            status="deceased",
        ),
    )
    correction = {
        **body,
        "request_id": str(uuid4()),
        "corrects_record_id": original["id"],
        "correction_reason": "Correcting output only",
        "sellable_units": 13,
    }
    corrected = market_client.post(path, headers=market_headers, json=correction)
    assert corrected.status_code == 201, corrected.text
    assert corrected.json()["livestock_snapshot"] == original["livestock_snapshot"]
    group_path = BASE + "/groups/" + livestock_group["id"]
    current = market_client.get(group_path + "/production-records", headers=market_headers).json()
    assert [row["id"] for row in current["items"]] == [corrected.json()["id"]]
    full = market_client.get(
        group_path + "/production-records?include_corrected=true&limit=1&offset=1",
        headers=market_headers,
    ).json()
    assert [row["id"] for row in full["items"]] == [original["id"]]
    changed = {
        **correction,
        "request_id": str(uuid4()),
        "corrects_record_id": corrected.json()["id"],
        "livestock_source": source("group", livestock_group),
        "correction_reason": "Correcting attribution to whole flock",
    }
    replacement = market_client.post(path, headers=market_headers, json=changed)
    assert replacement.status_code == 201
    assert replacement.json()["livestock_snapshot"]["kind"] == "group"
    assert (
        market_client.get(animal_path + "/production-records", headers=market_headers).json()[
            "items"
        ]
        == []
    )
    removed = market_client.post(
        path,
        headers=market_headers,
        json={
            **changed,
            "request_id": str(uuid4()),
            "corrects_record_id": replacement.json()["id"],
            "livestock_source": None,
            "correction_reason": "Source is now unknown",
        },
    )
    assert removed.status_code == 201 and removed.json()["livestock_snapshot"] is None
    assert (
        market_client.get(group_path + "/production-records", headers=market_headers).json()[
            "items"
        ]
        == []
    )


def test_attribution_ownership_revision_and_input_checks(
    market_client,
    market_headers,
    market_account,
    livestock_group,
    livestock_animal,
    livestock_product,
    livestock_production_body,
):
    other = market_account("other-livestock-source@example.com")
    private_group = market_client.post(
        BASE + "/groups",
        headers=other,
        json={
            "request_id": str(uuid4()),
            "name": "Other private flock",
            "species": "chicken",
            "occurred_on": "2025-01-01",
            "reason": "Demo registration",
        },
    ).json()["after"]
    path = livestock_product + "/production-records"
    for reference, status in (
        (source("group", private_group), 404),
        ({**source("group", livestock_group), "expected_revision": 2}, 409),
        ({**source("animal", livestock_animal), "id": str(uuid4())}, 404),
        ({**source("animal", livestock_animal), "expected_revision": True}, 422),
        ({**source("animal", livestock_animal), "kind": "flock"}, 422),
        ([source("group", livestock_group), source("animal", livestock_animal)], 422),
    ):
        response = market_client.post(
            path,
            headers=market_headers,
            json={
                **livestock_production_body,
                "livestock_source": reference,
            },
        )
        assert response.status_code == status, response.text
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ProductionRecord)) == 0
        assert db.scalar(select(func.count()).select_from(ProductionLivestockSource)) == 0
    # Same retry key remains usable after failed source validation.
    assert (
        market_client.post(
            path,
            headers=market_headers,
            json={
                **livestock_production_body,
                "livestock_source": source("animal", livestock_animal),
            },
        ).status_code
        == 201
    )


def test_source_and_record_rollback_together(
    market_client,
    market_headers,
    livestock_group,
    livestock_product,
    livestock_production_body,
    market_url,
):
    path = livestock_product + "/production-records"
    body = {**livestock_production_body, "livestock_source": source("group", livestock_group)}

    def fail(db):
        if any(isinstance(row, ProductionLivestockSource) for row in db.new):
            raise RuntimeError("Synthetic source persistence failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert client.post(path, headers=market_headers, json=body).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(ProductionRecord)) == 0
        assert db.scalar(select(func.count()).select_from(ProductionLivestockSource)) == 0
    assert market_client.post(path, headers=market_headers, json=body).status_code == 201


@pytest.mark.parametrize("kind", ["group", "animal"])
def test_unsourced_reports_remain_supported_and_old_requests_retry(
    market_client,
    market_headers,
    livestock_group,
    livestock_animal,
    livestock_product,
    livestock_production_body,
    kind,
):
    path = livestock_product + "/production-records"
    original = market_client.post(
        path, headers=market_headers, json=livestock_production_body
    ).json()
    assert original["livestock_snapshot"] is None
    # Simulate an immutable request saved by the previous release without the new optional key.
    with Session(market_client.app.state.engine) as db, db.begin():
        record = db.get(ProductionRecord, original["id"])
        legacy = dict(record.request)
        legacy.pop("livestock_source", None)
        record.request = legacy
    response = market_client.post(path, headers=market_headers, json=livestock_production_body)
    assert response.status_code == 200 and response.json()["livestock_snapshot"] is None
    profile = livestock_group if kind == "group" else livestock_animal
    sourced = market_client.post(
        path,
        headers=market_headers,
        json={
            **livestock_production_body,
            "livestock_source": source(kind, profile),
        },
    )
    assert sourced.status_code == 409  # Retry keys cannot retroactively add attribution.
