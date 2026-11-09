"""Group/individual identities, membership history, privacy and transaction behavior."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import (
    AccountRole,
    LivestockAnimal,
    LivestockAnimalEvent,
    LivestockGroup,
    LivestockGroupEvent,
)

BASE = "/api/v1/seller/livestock"


def replace_body(profile, **changes):
    fields = {
        key: value
        for key, value in profile.items()
        if key
        not in {
            "id",
            "species",
            "revision",
            "created_at",
            "updated_at",
            "basis",
            "registered_active_animals",
        }
    }
    return {
        **fields,
        "request_id": str(uuid4()),
        "expected_revision": profile["revision"],
        "occurred_on": date.today().isoformat(),
        "reason": "Synthetic profile correction or transfer",
        **changes,
    }


def test_group_count_is_distinct_from_registered_animals(
    market_client,
    market_headers,
    livestock_group,
    livestock_animal,
):
    group_path = BASE + "/groups/" + livestock_group["id"]
    group = market_client.get(group_path, headers=market_headers)
    assert group.status_code == 200 and group.headers["Cache-Control"] == "no-store"
    assert group.json()["reported_headcount"] == 30
    assert group.json()["registered_active_animals"] == 1
    assert group.json()["revision"] == 1
    assert "account_id" not in group.text and "access_token" not in group.text
    rows = market_client.get(BASE + "/groups", headers=market_headers).json()["items"]
    assert rows == [group.json()]
    animals = market_client.get(
        BASE + "/animals?group_id=" + livestock_group["id"], headers=market_headers
    ).json()["items"]
    assert animals == [livestock_animal]
    # Unknown counts are not synthesized from registration coverage.
    update = replace_body(livestock_group, reported_headcount=None, headcount_on=None)
    changed = market_client.put(group_path, headers=market_headers, json=update)
    assert changed.status_code == 200
    group = market_client.get(group_path, headers=market_headers).json()
    assert group["reported_headcount"] is None and group["registered_active_animals"] == 1


def test_transfer_departure_and_history_preserve_prior_membership(
    market_client,
    market_headers,
    livestock_group,
    livestock_animal,
    livestock_group_body,
):
    destination = market_client.post(
        BASE + "/groups",
        headers=market_headers,
        json={
            **livestock_group_body,
            "request_id": str(uuid4()),
            "name": "Second flock",
        },
    ).json()["after"]
    path = BASE + "/animals/" + livestock_animal["id"]
    transfer = replace_body(livestock_animal, group_id=destination["id"])
    moved = market_client.put(path, headers=market_headers, json=transfer)
    assert moved.status_code == 200, moved.text
    assert moved.json()["before"]["group_id"] == livestock_group["id"]
    assert moved.json()["after"]["group_id"] == destination["id"]
    departed = market_client.put(
        path,
        headers=market_headers,
        json=replace_body(
            moved.json()["after"],
            status="departed",
            group_id=None,
        ),
    )
    assert departed.status_code == 200
    history = market_client.get(path + "/history?limit=2", headers=market_headers).json()
    assert [row["revision"] for row in history["items"]] == [3, 2]
    original = market_client.get(path + "/history?offset=2", headers=market_headers).json()[
        "items"
    ][0]
    assert original["before"] is None and original["after"] == livestock_animal
    # Replaying the transfer returns the original event, not today's departed profile.
    retry = market_client.put(path, headers=market_headers, json=transfer)
    assert retry.json() == moved.json()
    assert market_client.get(path, headers=market_headers).json()["status"] == "departed"
    assert market_client.get(BASE + "/animals?status=departed", headers=market_headers).json()[
        "items"
    ]
    for group in (livestock_group, destination):
        current = market_client.get(BASE + "/groups/" + group["id"], headers=market_headers).json()
        assert current["registered_active_animals"] == 0 and current["reported_headcount"] == 30


def test_retry_uniqueness_and_stale_edits(
    market_client,
    market_headers,
    livestock_group_body,
    livestock_animal_body,
):
    for plural, body in (("groups", livestock_group_body), ("animals", livestock_animal_body)):
        path = BASE + "/" + plural
        first = market_client.post(path, headers=market_headers, json=body)
        assert first.status_code == 201, first.text
        profile = first.json()["after"]
        detail = path + "/" + profile["id"]
        changed_body = replace_body(profile, notes="Revision two")
        changed = market_client.put(detail, headers=market_headers, json=changed_body)
        assert changed.status_code == 200
        assert market_client.post(path, headers=market_headers, json=body).json() == first.json()
        stale = market_client.put(detail, headers=market_headers, json=replace_body(profile))
        assert stale.status_code == 409 and stale.json()["detail"]["code"] == "REVISION_CONFLICT"
        conflict = market_client.put(
            detail,
            headers=market_headers,
            json={
                **changed_body,
                "notes": "Changed retry content",
            },
        )
        assert conflict.status_code == 409
        key = "name" if plural == "groups" else "identifier"
        duplicate = market_client.post(
            path,
            headers=market_headers,
            json={
                **body,
                "request_id": str(uuid4()),
                key: body[key].lower(),
            },
        )
        assert duplicate.status_code == 409
        assert (
            len(market_client.get(detail + "/history", headers=market_headers).json()["items"]) == 2
        )


def test_group_archival_species_and_status_rules(
    market_client,
    market_headers,
    livestock_group,
    livestock_animal,
    livestock_group_body,
    livestock_animal_body,
):
    path = BASE + "/groups/" + livestock_group["id"]
    archived = replace_body(livestock_group, archived=True)
    blocked = market_client.put(path, headers=market_headers, json=archived)
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "GROUP_HAS_MEMBERS"
    other_species = market_client.post(
        BASE + "/animals",
        headers=market_headers,
        json={
            **livestock_animal_body,
            "request_id": str(uuid4()),
            "identifier": "Demo goat",
            "species": "Goat",
            "group_id": livestock_group["id"],
        },
    )
    assert (
        other_species.status_code == 409
        and other_species.json()["detail"]["code"] == "SPECIES_MISMATCH"
    )
    animal_path = BASE + "/animals/" + livestock_animal["id"]
    assert (
        market_client.put(
            animal_path,
            headers=market_headers,
            json=replace_body(
                livestock_animal,
                status="deceased",
                group_id=None,
            ),
        ).status_code
        == 200
    )
    assert market_client.put(path, headers=market_headers, json=archived).status_code == 200
    rejected = market_client.post(
        BASE + "/animals",
        headers=market_headers,
        json={
            **livestock_animal_body,
            "request_id": str(uuid4()),
            "identifier": "Another hen",
            "group_id": livestock_group["id"],
        },
    )
    assert rejected.status_code == 409 and rejected.json()["detail"]["code"] == "GROUP_ARCHIVED"
    assert (
        market_client.get(BASE + "/groups?archived=false", headers=market_headers).json()["items"]
        == []
    )
    assert (
        len(
            market_client.get(BASE + "/groups?archived=true", headers=market_headers).json()[
                "items"
            ]
        )
        == 1
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"reported_headcount": True},
        {"reported_headcount": -1},
        {"reported_headcount": 1000001},
        {"headcount_on": None},
        {"headcount_on": "2999-01-01"},
        {"name": " "},
        {"occurred_on": "2999-01-01"},
        {"reason": "\x00"},
        {"reason": " "},
        {"archived": "false"},
        {"account_id": "PRIVATE_BAD_OWNER"},
        {"notes": "x" * 2001},
    ],
)
def test_group_invalid_inputs_are_redacted(
    market_client, market_headers, livestock_group_body, changes
):
    response = market_client.post(
        BASE + "/groups", headers=market_headers, json={**livestock_group_body, **changes}
    )
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_BAD_OWNER" not in response.text
    assert all("input" not in item for item in response.json()["detail"])
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(LivestockGroup)) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"identifier": " "},
        {"species": " "},
        {"status": "unknown"},
        {"sex": "other"},
        {"born_on": "2999-01-01"},
        {"acquired_on": "2024-01-01"},
        {"status": "deceased", "group_id": "19000000-0000-4000-8000-000000000099"},
        {"group_id": "PRIVATE_BAD_ID"},
        {"revision": 1},
    ],
)
def test_animal_invalid_inputs_are_redacted(
    market_client, market_headers, livestock_animal_body, changes
):
    response = market_client.post(
        BASE + "/animals", headers=market_headers, json={**livestock_animal_body, **changes}
    )
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_BAD_ID" not in response.text


def test_roles_cross_seller_links_and_every_route(
    market_client,
    market_headers,
    market_account,
    livestock_group,
    livestock_animal,
    livestock_group_body,
    livestock_animal_body,
):
    group_path = BASE + "/groups/" + livestock_group["id"]
    animal_path = BASE + "/animals/" + livestock_animal["id"]
    buyer = market_account("livestock-buyer@example.com", roles=())
    admin = market_account("livestock-admin@example.com", roles=("admin",))
    other = market_account("livestock-other@example.com")
    routes = [
        ("get", group_path, None),
        ("get", group_path + "/history", None),
        ("get", group_path + "/production-records", None),
        ("put", group_path, replace_body(livestock_group)),
        ("get", animal_path, None),
        ("get", animal_path + "/history", None),
        ("get", animal_path + "/production-records", None),
        ("put", animal_path, replace_body(livestock_animal)),
    ]
    for headers, status in (({}, 401), (buyer, 403), (admin, 403), (other, 404)):
        for method, path, body in routes:
            kwargs = {"json": body} if body else {}
            response = market_client.request(method, path, headers=headers, **kwargs)
            assert response.status_code == status
            assert response.headers["Cache-Control"] == "no-store"
            if status == 401:
                assert response.headers["WWW-Authenticate"] == "Bearer"
    for headers, status in (({}, 401), (buyer, 403), (admin, 403)):
        for plural, body in (("groups", livestock_group_body), ("animals", livestock_animal_body)):
            assert market_client.get(BASE + "/" + plural, headers=headers).status_code == status
            assert (
                market_client.post(BASE + "/" + plural, headers=headers, json=body).status_code
                == status
            )
    for plural in ("groups", "animals"):
        assert market_client.get(BASE + "/" + plural, headers=other).json()["items"] == []
    cross_link = market_client.post(
        BASE + "/animals",
        headers=other,
        json={
            **livestock_animal_body,
            "group_id": livestock_group["id"],
        },
    )
    assert cross_link.status_code == 404
    assert (
        market_client.get(
            BASE + "/animals?group_id=" + livestock_group["id"], headers=other
        ).status_code
        == 404
    )


def test_concurrent_retries_edits_and_rollback(
    market_client,
    market_headers,
    livestock_group_body,
    market_url,
):
    path = BASE + "/groups"
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda _: market_client.post(
                    path, headers=market_headers, json=livestock_group_body
                ),
                range(2),
            )
        )
    assert sorted(reply.status_code for reply in replies) == [200, 201]
    assert replies[0].json() == replies[1].json()
    profile = replies[0].json()["after"]
    path += "/" + profile["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda body: market_client.put(path, headers=market_headers, json=body),
                [replace_body(profile, notes="One"), replace_body(profile, notes="Two")],
            )
        )
    assert sorted(reply.status_code for reply in replies) == [200, 409]
    profile = market_client.get(path, headers=market_headers).json()
    body = replace_body(profile, notes="After failed commit")

    def fail(db):
        if any(isinstance(row, LivestockGroupEvent) for row in db.new):
            raise RuntimeError("Synthetic livestock commit failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert client.put(path, headers=market_headers, json=body).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert market_client.get(path, headers=market_headers).json() == profile
    assert market_client.put(path, headers=market_headers, json=body).status_code == 200
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(LivestockGroupEvent)) == 3


def test_revoked_seller_grant_is_rechecked_after_reservation(
    market_client,
    market_headers,
    livestock_group,
    monkeypatch,
):
    from fairmade.livestock import service

    original = service.reserve_seller_account

    def revoke(db, account_id):
        db.delete(db.get(AccountRole, (account_id, "seller")))
        db.flush()
        original(db, account_id)

    monkeypatch.setattr(service, "reserve_seller_account", revoke)
    response = market_client.put(
        BASE + "/groups/" + livestock_group["id"],
        headers=market_headers,
        json=replace_body(livestock_group),
    )
    assert response.status_code == 403
    with Session(market_client.app.state.engine) as db:
        assert db.get(LivestockGroup, livestock_group["id"]).revision == 1
        assert db.scalar(select(func.count()).select_from(LivestockAnimalEvent)) == 0
        assert db.scalar(select(func.count()).select_from(LivestockAnimal)) == 0


def test_openapi_bounds_and_no_public_routes(market_client, market_headers, livestock_group):
    schema = market_client.get("/openapi.json").json()
    routes = {path: methods for path, methods in schema["paths"].items() if "/livestock" in path}
    assert len(routes) == 8
    for path, methods in routes.items():
        assert path.startswith(BASE)
        assert all(method["security"] == [{"HTTPBearer": []}] for method in methods.values())
    for plural in ("groups", "animals"):
        for query in ("limit=101", "offset=-1", "limit=0"):
            assert (
                market_client.get(
                    BASE + "/" + plural + "?" + query, headers=market_headers
                ).status_code
                == 422
            )
    for query in ("archived=invalid",):
        assert (
            market_client.get(BASE + "/groups?" + query, headers=market_headers).status_code == 422
        )


def test_archive_and_registration_cannot_leave_members_in_archived_group(
    market_client,
    market_headers,
    livestock_group,
    livestock_animal_body,
):
    path = BASE + "/groups/" + livestock_group["id"]
    archive = replace_body(livestock_group, archived=True)
    animal = {**livestock_animal_body, "group_id": livestock_group["id"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        archiving = pool.submit(market_client.put, path, headers=market_headers, json=archive)
        registration = pool.submit(
            market_client.post, BASE + "/animals", headers=market_headers, json=animal
        )
        archive_response, animal_response = archiving.result(), registration.result()
    assert (archive_response.status_code, animal_response.status_code) in ((200, 409), (409, 201))
    current = market_client.get(path, headers=market_headers).json()
    assert not (current["archived"] and current["registered_active_animals"])


def test_individual_concurrent_retries_and_changes(
    market_client,
    market_headers,
    livestock_animal_body,
):
    path = BASE + "/animals"
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda _: market_client.post(
                    path, headers=market_headers, json=livestock_animal_body
                ),
                range(2),
            )
        )
    assert sorted(reply.status_code for reply in replies) == [200, 201]
    assert replies[0].json() == replies[1].json()
    profile = replies[0].json()["after"]
    path += "/" + profile["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda body: market_client.put(path, headers=market_headers, json=body),
                [
                    replace_body(profile, name="First edit"),
                    replace_body(profile, name="Second edit"),
                ],
            )
        )
    assert sorted(reply.status_code for reply in replies) == [200, 409]
    assert len(market_client.get(path + "/history", headers=market_headers).json()["items"]) == 2
