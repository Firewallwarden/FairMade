"""Seller-controlled publication, single-store scope and private/public separation."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AccountRole, Storefront

PRIVATE = "/api/v1/seller/storefronts"
PUBLIC = "/api/v1/storefronts"
BACKEND = Path(__file__).parents[2]


@pytest.fixture
def content():
    return {
        "display_name": "Example bakery",
        "description": "Synthetic business profile.",
        "location": "Exampletown",
    }


@pytest.fixture
def storefront(market_client, market_headers, content):
    response = market_client.post(PRIVATE, headers=market_headers, json=content)
    assert response.status_code == 201, response.text
    return response.json()


def approval(client, headers, profile_id):
    response = client.get(PRIVATE + "/" + profile_id + "/preview", headers=headers)
    assert response.status_code == 200, response.text
    preview = response.json()
    return {
        "expected_revision": preview["revision"],
        "preview_hash": preview["preview_hash"],
        "approved": True,
    }


def publish(client, headers, profile_id):
    response = client.post(
        PRIVATE + "/" + profile_id + "/publish",
        headers=headers,
        json=approval(client, headers, profile_id),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_draft_hidden_until_exact_approval_and_public_id_is_independent(
    market_client,
    market_headers,
    storefront,
):
    assert storefront["revision"] == 1 and storefront["state"] == "draft"
    assert storefront["published_revision"] is None
    assert (
        storefront["id"]
        != market_client.get("/api/v1/auth/me", headers=market_headers).json()["id"]
    )
    assert market_client.get(PRIVATE, headers=market_headers).json()["items"] == [storefront]
    assert market_client.get(PUBLIC).json()["items"] == []
    assert market_client.get(PUBLIC + "/" + storefront["id"]).status_code == 404
    assert market_client.get(PUBLIC + "/" + storefront["id"] + "/listings").status_code == 404
    public = publish(market_client, market_headers, storefront["id"])
    assert public["payload"]["display_name"] == "Example bakery"
    assert public["payload"]["basis"] == "seller_reported_unverified"
    assert public["published_revision"] == 1
    response = market_client.get(PUBLIC + "/" + storefront["id"])
    assert response.json() == public
    assert response.headers["Cache-Control"] == "no-store"
    assert public["published_at"].endswith("Z")
    assert storefront["created_at"].endswith("Z")


def test_second_storefront_is_rejected_for_same_seller(
    market_client,
    market_headers,
    storefront,
    content,
):
    response = market_client.post(
        PRIVATE, headers=market_headers, json={**content, "display_name": "Second brand"}
    )
    assert response.status_code == 409 and response.json()["detail"]["code"] == "STOREFRONT_LIMIT"
    with Session(market_client.app.state.engine) as db:
        assert len(db.scalars(select(Storefront)).all()) == 1


def test_duplicate_creation_race_is_atomic(market_client, market_headers, content):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: market_client.post(PRIVATE, headers=market_headers, json=content),
                range(2),
            )
        )
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert len(market_client.get(PRIVATE, headers=market_headers).json()["items"]) == 1


def test_draft_edits_do_not_change_public_content_search_or_location(
    market_client,
    market_headers,
    storefront,
):
    profile_id = storefront["id"]
    original = publish(market_client, market_headers, profile_id)
    changed = market_client.put(
        PRIVATE + "/" + profile_id,
        headers=market_headers,
        json={
            "expected_revision": 1,
            "display_name": "PRIVATE_DRAFT_NAME",
            "description": "PRIVATE_DRAFT_TEXT",
            "location": "PRIVATE_DRAFT_TOWN",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["revision"] == 2 and changed.json()["published_revision"] == 1
    assert market_client.get(PUBLIC + "/" + profile_id).json() == original
    assert market_client.get(PUBLIC + "?q=PRIVATE_DRAFT").json()["items"] == []
    assert market_client.get(PUBLIC + "?location=PRIVATE_DRAFT_TOWN").json()["items"] == []
    updated = publish(market_client, market_headers, profile_id)
    assert updated["published_revision"] == 2
    assert updated["payload"]["display_name"] == "PRIVATE_DRAFT_NAME"
    assert len(market_client.get(PUBLIC + "?q=PRIVATE_DRAFT").json()["items"]) == 1
    assert market_client.get(PUBLIC + "?location=Exampletown").json()["items"] == []


def test_stale_revision_wrong_hash_and_implicit_approval_are_rejected(
    market_client,
    market_headers,
    storefront,
    content,
):
    profile_id = storefront["id"]
    body = approval(market_client, market_headers, profile_id)
    response = market_client.post(
        PRIVATE + "/" + profile_id + "/publish",
        headers=market_headers,
        json={**body, "preview_hash": "0" * 64},
    )
    assert response.status_code == 409 and response.json()["detail"]["code"] == "PREVIEW_MISMATCH"
    for value in (False, 1, "true"):
        assert (
            market_client.post(
                PRIVATE + "/" + profile_id + "/publish",
                headers=market_headers,
                json={**body, "approved": value},
            ).status_code
            == 422
        )
    assert (
        market_client.put(
            PRIVATE + "/" + profile_id,
            headers=market_headers,
            json={**content, "display_name": "Edited", "expected_revision": 1},
        ).status_code
        == 200
    )
    assert (
        market_client.post(
            PRIVATE + "/" + profile_id + "/publish",
            headers=market_headers,
            json=body,
        ).status_code
        == 409
    )
    assert (
        market_client.put(
            PRIVATE + "/" + profile_id,
            headers=market_headers,
            json={**content, "expected_revision": 1},
        ).status_code
        == 409
    )


def test_idempotent_publish_and_withdraw_invalidate_previous_approval(
    market_client,
    market_headers,
    storefront,
    content,
):
    profile_id = storefront["id"]
    body = approval(market_client, market_headers, profile_id)
    original = publish(market_client, market_headers, profile_id)
    retry = market_client.post(
        PRIVATE + "/" + profile_id + "/publish", headers=market_headers, json=body
    )
    assert retry.status_code == 200 and retry.json() == original
    for _ in range(2):
        response = market_client.post(
            PRIVATE + "/" + profile_id + "/withdraw", headers=market_headers
        )
        assert response.status_code == 204 and response.content == b""
    current = market_client.get(PRIVATE + "/" + profile_id, headers=market_headers).json()
    assert current["revision"] == 2 and current["state"] == "withdrawn"
    assert market_client.get(PUBLIC + "/" + profile_id).status_code == 404
    assert (
        market_client.post(
            PRIVATE + "/" + profile_id + "/publish",
            headers=market_headers,
            json=body,
        ).status_code
        == 409
    )
    assert market_client.post(PRIVATE, headers=market_headers, json=content).status_code == 409
    assert publish(market_client, market_headers, profile_id)["published_revision"] == 2


def test_private_routes_require_verified_owner_and_do_not_expose_identifiers(
    market_client,
    market_headers,
    market_account,
    storefront,
    content,
):
    path = PRIVATE + "/" + storefront["id"]
    body = approval(market_client, market_headers, storefront["id"])
    buyer = market_account("storefront-buyer@example.com", roles=())
    admin = market_account("storefront-admin@example.com", roles=("admin",))
    other = market_account("storefront-other@example.com")
    for headers, code in (({}, 401), (buyer, 403), (admin, 403)):
        assert market_client.post(PRIVATE, headers=headers, json=content).status_code == code
        assert market_client.get(PRIVATE, headers=headers).status_code == code
        assert market_client.get(path, headers=headers).status_code == code
    for headers, code in (({}, 401), (buyer, 403), (other, 404)):
        for method, url, data in (
            ("get", path, None),
            ("get", path + "/preview", None),
            ("put", path, {**content, "expected_revision": 1}),
            ("post", path + "/publish", body),
            ("post", path + "/withdraw", None),
        ):
            assert (
                market_client.request(method, url, headers=headers, json=data).status_code == code
            )
    assert market_client.get(PRIVATE, headers=other).json()["items"] == []
    public = publish(market_client, market_headers, storefront["id"])
    text = market_client.get(PUBLIC).text
    assert "account_id" not in text and "email" not in text and "password" not in text
    assert "content" not in public and "revision" not in public


def test_loss_of_seller_access_hides_all_public_storefront_views(
    market_client,
    market_headers,
    storefront,
    order_source,
):
    profile_id = storefront["id"]
    publish(market_client, market_headers, profile_id)
    assert len(market_client.get(PUBLIC + "/" + profile_id + "/listings").json()["items"]) == 1
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
    assert market_client.get(PUBLIC).json()["items"] == []
    assert market_client.get(PUBLIC + "/" + profile_id).status_code == 404
    assert market_client.get(PUBLIC + "/" + profile_id + "/listings").status_code == 404
    assert market_client.get(PRIVATE, headers=market_headers).status_code == 403


def test_storefront_lists_only_owners_visible_listings_and_keeps_approved_names(
    market_client,
    market_headers,
    market_account,
    storefront,
    order_source,
    market_source,
):
    profile_id = storefront["id"]
    publish(market_client, market_headers, profile_id)
    other_headers = market_account("another-store-owner@example.com")
    other = market_source(headers=other_headers, title="Other public loaf")
    listing = market_client.post(
        other["path"] + "/listing",
        headers=other_headers,
        json={
            "passport_publication_id": other["publication"]["id"],
            "selling_quantity": {"value": "1", "unit": "item"},
            "seller_display_name": "Other",
        },
    )
    assert listing.status_code == 201
    preview = market_client.get(other["path"] + "/listing/preview", headers=other_headers).json()
    market_client.post(
        other["path"] + "/listing/activate",
        headers=other_headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    )
    response = market_client.get(PUBLIC + "/" + profile_id + "/listings")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["items"]] == [order_source["listing"]["id"]]
    assert response.json()["items"][0]["payload"]["seller_display_name"] == "Example bakery"
    market_client.put(
        PRIVATE + "/" + profile_id,
        headers=market_headers,
        json={"expected_revision": 1, "display_name": "New storefront name"},
    )
    publish(market_client, market_headers, profile_id)
    cards = market_client.get(PUBLIC + "/" + profile_id + "/listings").json()["items"]
    assert cards[0]["payload"]["seller_display_name"] == "Example bakery"
    assert "PRIVATE_MARKET" not in response.text
    market_client.post(order_source["path"] + "/listing/deactivate", headers=market_headers)
    assert market_client.get(PUBLIC + "/" + profile_id + "/listings").json()["items"] == []


def test_storefront_withdrawal_does_not_deactivate_separate_listings(
    market_client,
    market_headers,
    storefront,
    order_source,
):
    publish(market_client, market_headers, storefront["id"])
    market_client.post(PRIVATE + "/" + storefront["id"] + "/withdraw", headers=market_headers)
    assert market_client.get(PUBLIC + "/" + storefront["id"]).status_code == 404
    assert (
        market_client.get(
            "/api/v1/marketplace/listings/" + order_source["listing"]["id"]
        ).status_code
        == 200
    )


def test_browse_filters_and_bounded_pages_use_only_published_fields(
    market_client,
    market_headers,
    storefront,
):
    publish(market_client, market_headers, storefront["id"])
    for query in ("q=BAKERY", "location=exampletown", "q=Example&location=Exampletown"):
        assert len(market_client.get(PUBLIC + "?" + query).json()["items"]) == 1
    for query in ("q=%", "q=_", "location=OtherTown", "limit=1&offset=1"):
        assert market_client.get(PUBLIC + "?" + query).json()["items"] == []
    for query in ("limit=101", "offset=-1", "q=", "q=" + "a" * 201):
        assert market_client.get(PUBLIC + "?" + query).status_code == 422
    assert (
        market_client.get(PRIVATE + "?limit=1&offset=1", headers=market_headers).json()["items"]
        == []
    )


def test_empty_storefront_and_missing_resource_are_safe(market_client, market_headers, storefront):
    publish(market_client, market_headers, storefront["id"])
    assert market_client.get(PUBLIC + "/" + storefront["id"] + "/listings").json()["items"] == []
    for suffix in ("", "/listings"):
        assert market_client.get(PUBLIC + "/" + str(uuid4()) + suffix).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"display_name": " "},
        {"display_name": "a" * 201},
        {"description": "a" * 2001},
        {"account_id": "PRIVATE_VALUE"},
        {"verified": True},
        {"published_revision": 1},
    ],
)
def test_creation_is_strict_and_validation_does_not_echo_values(
    market_client,
    market_headers,
    content,
    changes,
):
    response = market_client.post(PRIVATE, headers=market_headers, json={**content, **changes})
    assert response.status_code == 422
    assert "PRIVATE_VALUE" not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_competing_edits_preserve_one_revision(market_client, market_headers, storefront, content):
    def edit(name):
        return market_client.put(
            PRIVATE + "/" + storefront["id"],
            headers=market_headers,
            json={**content, "display_name": name, "expected_revision": 1},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(edit, ["First", "Second"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert (
        market_client.get(PRIVATE + "/" + storefront["id"], headers=market_headers).json()[
            "revision"
        ]
        == 2
    )


def test_publish_racing_edit_never_publishes_unapproved_content(
    market_client,
    market_headers,
    storefront,
    content,
):
    profile_id = storefront["id"]
    approved = approval(market_client, market_headers, profile_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        publish_future = pool.submit(
            market_client.post,
            PRIVATE + "/" + profile_id + "/publish",
            headers=market_headers,
            json=approved,
        )
        edit_future = pool.submit(
            market_client.put,
            PRIVATE + "/" + profile_id,
            headers=market_headers,
            json={**content, "display_name": "UNAPPROVED_RACING_NAME", "expected_revision": 1},
        )
        published, edited = publish_future.result(), edit_future.result()
    assert edited.status_code == 200
    assert published.status_code in (200, 409)
    public = market_client.get(PUBLIC + "/" + profile_id)
    assert "UNAPPROVED_RACING_NAME" not in public.text
    if public.status_code == 200:
        assert public.json()["payload"]["display_name"] == content["display_name"]
    else:
        assert public.status_code == 404


def test_failed_publication_commit_does_not_expose_draft(
    market_client,
    market_headers,
    storefront,
    market_url,
):
    body = approval(market_client, market_headers, storefront["id"])

    def fail(db):
        if any(isinstance(item, Storefront) and item.state == "published" for item in db.dirty):
            raise RuntimeError("Synthetic storefront publication persistence failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            response = client.post(
                PRIVATE + "/" + storefront["id"] + "/publish", headers=market_headers, json=body
            )
            assert response.status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert market_client.get(PUBLIC).json()["items"] == []
    assert (
        market_client.get(PRIVATE + "/" + storefront["id"], headers=market_headers).json()["state"]
        == "draft"
    )


def test_restart_metadata_and_downgrade_guard_preserve_profile(
    market_client,
    market_headers,
    storefront,
    market_url,
):
    public = publish(market_client, market_headers, storefront["id"])
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="storefront records"):
        command.downgrade(config, "0013")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(PUBLIC + "/" + storefront["id"]).json() == public
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_empty_migration_roundtrip_preserves_prior_account(market_client, market_headers):
    config = Config(str(BACKEND / "alembic.ini"))
    before = market_client.get("/api/v1/auth/me", headers=market_headers).json()
    command.downgrade(config, "0013")
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get("/api/v1/auth/me", headers=market_headers).json() == before


def test_openapi_keeps_private_and_public_auth_separate(market_client):
    schema = market_client.get("/openapi.json").json()
    for path, operations in schema["paths"].items():
        if path.startswith(PRIVATE):
            for operation in operations.values():
                assert operation["security"] == [{"HTTPBearer": []}]
                assert {"401", "403", "404", "409", "422"} <= set(operation["responses"])
        elif path.startswith(PUBLIC):
            for operation in operations.values():
                assert "security" not in operation
    public_fields = schema["components"]["schemas"]["PublicStorefront"]["properties"]
    assert set(public_fields) == {
        "id",
        "published_revision",
        "published_at",
        "payload_hash",
        "payload",
    }
