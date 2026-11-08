"""Approved-area privacy, discovery filters, lifecycle, bounds and migration preservation."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, text
from sqlalchemy.orm import Session

from fairmade.database import make_engine
from fairmade.discovery import repository
from fairmade.main import create_app
from fairmade.models import AccountRole, Storefront, StorefrontDiscoveryLocation

PRIVATE = "/api/v1/seller/storefronts"
PUBLIC = "/api/v1/storefronts"
DISCOVERY = "/api/v1/discovery"
BACKEND = Path(__file__).parents[2]


def approve(client, headers, profile_id):
    path = PRIVATE + "/" + profile_id
    preview = client.get(path + "/preview", headers=headers).json()
    return client.post(
        path + "/publish",
        headers=headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    )


@pytest.fixture
def profile_factory(market_client, market_headers):
    def create(latitude="0.00", longitude="0.00", *, headers=None, publish=True, area=True):
        headers = headers or market_headers
        content = {"display_name": "Example bakery", "location": "Exampletown"}
        if area:
            content["approximate_area"] = {
                "label": "Exampletown area",
                "latitude": latitude,
                "longitude": longitude,
            }
        response = market_client.post(PRIVATE, headers=headers, json=content)
        assert response.status_code == 201, response.text
        profile = response.json()
        if publish:
            result = approve(market_client, headers, profile["id"])
            assert result.status_code == 200, result.text
        return profile

    return create


@pytest.fixture
def search():
    return {"origin": {"latitude": "0", "longitude": "0"}, "radius_km": "25"}


def find(client, body, kind="storefronts"):
    response = client.post(DISCOVERY + "/" + kind, json=body)
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()


def test_area_is_opt_in_and_only_exact_approved_publication_is_searchable(
    market_client,
    market_headers,
    profile_factory,
    search,
):
    profile = profile_factory(publish=False)
    assert find(market_client, search)["items"] == []
    published = approve(market_client, market_headers, profile["id"]).json()
    result = find(market_client, search)
    assert result["distance_basis"] == "approximate_area_great_circle"
    assert result["items"] == [{"storefront": published, "estimated_distance_km": "0.0"}]
    assert published["payload"]["approximate_area"]["basis"] == "seller_chosen_approximate"
    assert "origin" not in result and "radius_km" not in result
    for secret in ("account_id", "email", "password", "content", "latitude_hundredths"):
        assert secret not in str(result)
    original = market_client.get(PUBLIC + "/" + profile["id"]).json()
    replacement = {**profile["content"], "expected_revision": 1}
    replacement["approximate_area"] = {
        "label": "PRIVATE_DRAFT_AREA",
        "latitude": "20.00",
        "longitude": "20.00",
    }
    assert (
        market_client.put(
            PRIVATE + "/" + profile["id"], headers=market_headers, json=replacement
        ).status_code
        == 200
    )
    assert find(market_client, search)["items"][0]["storefront"] == original
    new_search = {**search, "origin": {"latitude": "20", "longitude": "20"}}
    assert find(market_client, new_search)["items"] == []
    assert approve(market_client, market_headers, profile["id"]).status_code == 200
    assert find(market_client, search)["items"] == []
    assert len(find(market_client, new_search)["items"]) == 1


def test_existing_profile_without_point_stays_in_regular_browse(
    market_client,
    profile_factory,
    search,
):
    profile = profile_factory(area=False)
    assert len(market_client.get(PUBLIC).json()["items"]) == 1
    assert find(market_client, search)["items"] == []
    with Session(market_client.app.state.engine) as db:
        assert db.get(StorefrontDiscoveryLocation, profile["id"]) is None


def test_removing_area_requires_approval_and_clears_search_index(
    market_client,
    market_headers,
    profile_factory,
    search,
):
    profile = profile_factory()
    assert (
        market_client.put(
            PRIVATE + "/" + profile["id"],
            headers=market_headers,
            json={"display_name": "Example", "expected_revision": 1},
        ).status_code
        == 200
    )
    assert len(find(market_client, search)["items"]) == 1
    assert approve(market_client, market_headers, profile["id"]).status_code == 200
    assert find(market_client, search)["items"] == []
    with Session(market_client.app.state.engine) as db:
        assert db.get(StorefrontDiscoveryLocation, profile["id"]) is None


def test_radius_nearest_order_pagination_and_literal_filters(
    market_client,
    market_account,
    profile_factory,
    search,
):
    far_headers = market_account("far@example.com")
    nearest = profile_factory("0", "0.01")
    farther = profile_factory("0", "0.10", headers=far_headers)
    third_headers = market_account("outside@example.com")
    profile_factory("0", "0.30", headers=third_headers)
    rows = find(market_client, search)["items"]
    assert [row["storefront"]["id"] for row in rows] == [nearest["id"], farther["id"]]
    assert [row["estimated_distance_km"] for row in rows] == ["1.1", "11.1"]
    assert find(market_client, {**search, "limit": 1, "offset": 1})["items"] == [rows[1]]
    assert find(market_client, {**search, "radius_km": "10"})["items"] == [rows[0]]
    assert find(market_client, {**search, "q": "BAKERY"})["items"] == rows
    assert find(market_client, {**search, "q": "%"})["items"] == []
    assert find(market_client, {**search, "offset": 3_000_000_000})["items"] == []


@pytest.mark.parametrize(
    ("latitude", "longitude", "origin"),
    [
        ("0", "-179.99", {"latitude": "0", "longitude": "179.99"}),
        ("90", "-180", {"latitude": "90", "longitude": "0"}),
        ("-90", "180", {"latitude": "-90", "longitude": "0"}),
    ],
)
def test_dateline_and_pole_candidates_are_not_missed(
    market_client,
    profile_factory,
    search,
    latitude,
    longitude,
    origin,
):
    profile = profile_factory(latitude, longitude)
    assert (
        find(market_client, {**search, "origin": origin})["items"][0]["storefront"]["id"]
        == profile["id"]
    )


def test_bounding_box_corner_is_excluded_by_actual_radius(market_client, profile_factory, search):
    profile_factory("0.20", "0.20")
    assert find(market_client, search)["items"] == []


def test_withdrawal_and_loss_of_seller_role_hide_results(
    market_client,
    market_headers,
    profile_factory,
    search,
    order_source,
):
    profile = profile_factory()
    assert len(find(market_client, search, "listings")["items"]) == 1
    market_client.post(PRIVATE + "/" + profile["id"] + "/withdraw", headers=market_headers)
    assert find(market_client, search)["items"] == []
    assert find(market_client, search, "listings")["items"] == []
    assert approve(market_client, market_headers, profile["id"]).status_code == 200
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
    assert find(market_client, search)["items"] == []
    assert find(market_client, search, "listings")["items"] == []


def test_nearby_listing_uses_current_visibility_and_approved_listing_not_profile_identity(
    market_client,
    market_headers,
    profile_factory,
    search,
    order_source,
):
    profile = profile_factory()
    rows = find(market_client, search, "listings")["items"]
    assert len(rows) == 1
    row = rows[0]
    assert row["listing"]["id"] == order_source["listing"]["id"]
    assert row["storefront_id"] == profile["id"]
    assert row["listing"]["payload"]["seller_display_name"] == "Example bakery"
    assert "PRIVATE_MARKET" not in str(row)
    assert find(market_client, {**search, "product_type": "eggs"}, "listings")["items"] == []
    assert (
        len(find(market_client, {**search, "product_type": "sourdough"}, "listings")["items"]) == 1
    )
    assert find(market_client, {**search, "q": "%"}, "listings")["items"] == []
    response = market_client.post(
        order_source["draft_url"]
        + "/publications/"
        + order_source["publication"]["id"]
        + "/withdraw",
        headers=market_headers,
    )
    assert response.status_code == 204
    assert find(market_client, search, "listings")["items"] == []


@pytest.mark.parametrize(
    "override",
    [
        {"radius_km": "0"},
        {"radius_km": "501"},
        {"radius_km": "NaN"},
        {"radius_km": "12.34"},
        {"origin": {"latitude": "91", "longitude": "0"}},
        {"origin": {"latitude": "0", "longitude": "181"}},
        {"origin": {"latitude": "0.1234567", "longitude": "0"}},
        {"origin": {"latitude": "0", "longitude": "Infinity"}},
        {"limit": 101},
        {"offset": -1},
        {"offset": 2**64},
        {"limit": True},
        {"q": " "},
        {"unexpected": "PRIVATE_LOCATION_SENTINEL"},
    ],
)
def test_invalid_search_redacts_inputs_and_is_not_cached(market_client, search, override):
    response = market_client.post(DISCOVERY + "/storefronts", json={**search, **override})
    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_LOCATION_SENTINEL" not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])


@pytest.mark.parametrize(
    "override",
    [
        {"latitude": "0.001"},
        {"longitude": "0.001"},
        {"latitude": "NaN"},
        {"latitude": "-91"},
        {"longitude": "-181"},
        {"label": " "},
        {"address": "PRIVATE_ADDRESS"},
    ],
)
def test_area_rejects_precise_invalid_or_extra_fields(market_client, market_headers, override):
    area = {"label": "Example area", "latitude": "0", "longitude": "0", **override}
    response = market_client.post(
        PRIVATE, headers=market_headers, json={"display_name": "Example", "approximate_area": area}
    )
    assert response.status_code == 422
    assert "PRIVATE_ADDRESS" not in response.text


def test_candidate_overflow_is_explicit_not_a_truncated_page(
    market_client,
    profile_factory,
    search,
    order_source,
    monkeypatch,
):
    profile_factory()
    monkeypatch.setattr(repository, "MAX_CANDIDATES", 0)
    for kind in ("storefronts", "listings"):
        response = market_client.post(DISCOVERY + "/" + kind, json=search)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "SEARCH_TOO_BROAD"
        assert response.headers["Cache-Control"] == "no-store"


def test_failed_publication_rolls_back_area_and_payload_together(
    market_client,
    market_headers,
    profile_factory,
    search,
    market_url,
):
    profile = profile_factory(publish=False)

    def fail(db):
        if any(isinstance(row, Storefront) and row.state == "published" for row in db.dirty):
            raise RuntimeError("Synthetic publish failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert approve(client, market_headers, profile["id"]).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert find(market_client, search)["items"] == []
    with Session(market_client.app.state.engine) as db:
        assert db.get(StorefrontDiscoveryLocation, profile["id"]) is None


def test_restart_schema_and_downgrade_guard_preserve_approved_area(
    market_client,
    profile_factory,
    search,
    market_url,
):
    profile_factory()
    expected = find(market_client, search)
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="storefront records"):
        command.downgrade(config, "0014")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert find(restarted, search) == expected
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == ScriptDirectory.from_config(config).get_current_head()
        )


def test_openapi_and_read_only_search_do_not_persist_buyer_location(
    market_client,
    profile_factory,
    search,
):
    profile_factory()
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.strip().split()[0].upper())

    event.listen(market_client.app.state.engine, "before_cursor_execute", record)
    try:
        for kind in ("storefronts", "listings"):
            result = find(
                market_client,
                {**search, "origin": {"latitude": "0.123456", "longitude": "0.123456"}},
                kind,
            )
            assert "0.123456" not in str(result)
    finally:
        event.remove(market_client.app.state.engine, "before_cursor_execute", record)
    assert statements and set(statements) == {"SELECT"}
    schema = market_client.get("/openapi.json").json()
    for kind in ("storefronts", "listings"):
        operation = schema["paths"][DISCOVERY + "/" + kind]["post"]
        assert "security" not in operation and "parameters" not in operation
        assert {"200", "409", "422"} <= set(operation["responses"])


def test_tied_distances_use_stable_resource_id_order(
    market_client,
    market_account,
    profile_factory,
    search,
):
    first = profile_factory()
    second = profile_factory(headers=market_account("same-area@example.com"))
    expected = sorted([first["id"], second["id"]])
    assert [row["storefront"]["id"] for row in find(market_client, search)["items"]] == expected


def test_stale_area_approval_is_rejected_and_retry_keeps_public_hash(
    market_client,
    market_headers,
    profile_factory,
    search,
):
    profile = profile_factory(publish=False)
    path = PRIVATE + "/" + profile["id"]
    old_preview = market_client.get(path + "/preview", headers=market_headers).json()
    replacement = {**profile["content"], "expected_revision": 1}
    replacement["approximate_area"] = {
        "label": "Different area",
        "latitude": "1.00",
        "longitude": "1.00",
    }
    assert market_client.put(path, headers=market_headers, json=replacement).status_code == 200
    response = market_client.post(
        path + "/publish",
        headers=market_headers,
        json={
            "expected_revision": 2,
            "preview_hash": old_preview["preview_hash"],
            "approved": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PREVIEW_MISMATCH"
    with Session(market_client.app.state.engine) as db:
        assert db.get(StorefrontDiscoveryLocation, profile["id"]) is None
    published = approve(market_client, market_headers, profile["id"])
    assert published.status_code == 200
    assert approve(market_client, market_headers, profile["id"]).json() == published.json()


def test_upgrade_preserves_old_publication_and_does_not_infer_coordinates(
    market_client,
    profile_factory,
    search,
    tmp_path,
    monkeypatch,
):
    profile = profile_factory(area=False)
    # Build an actual old schema, instead of dropping whichever newer tables happen
    # to exist. This keeps the upgrade check valid as later migrations are added.
    tables = ("accounts", "account_roles", "storefronts")
    with market_client.app.state.engine.connect() as connection:
        records = {
            table: connection.execute(text(f"SELECT * FROM {table}")).mappings().all()
            for table in tables
        }
    legacy_url = "sqlite:///" + (tmp_path / "legacy.sqlite3").as_posix()
    monkeypatch.setenv("FAIRMADE_DATABASE_URL", legacy_url)
    config = Config(str(BACKEND / "alembic.ini"))
    command.upgrade(config, "0014")
    engine = make_engine(legacy_url)
    try:
        with engine.begin() as connection:
            for table in tables:
                for row in records[table]:
                    columns = ", ".join(row.keys())
                    values = ", ".join(":" + name for name in row.keys())
                    connection.execute(
                        text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), dict(row)
                    )
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT * FROM storefronts")).mappings().all()
                == records["storefronts"]
            )
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM storefront_discovery_locations")
                ).scalar_one()
                == 0
            )
        with TestClient(create_app(legacy_url)) as legacy:
            assert legacy.get(PUBLIC + "/" + profile["id"]).status_code == 200
            assert find(legacy, search)["items"] == []
    finally:
        engine.dispose()
