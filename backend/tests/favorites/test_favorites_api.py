"""Private bookmarks, atomic duplicate saves and current publication visibility."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AccountRole, Favorite

FAVORITES = "/api/v1/favorites"
BACKEND = Path(__file__).parents[2]


def save(client, headers, listing_id):
    return client.post(FAVORITES, headers=headers, json={"listing_id": listing_id})


@pytest.fixture
def saved(market_client, buyer_headers, order_source):
    response = save(market_client, buyer_headers, order_source["listing"]["id"])
    assert response.status_code == 201, response.text
    return response.json()


def test_save_list_read_remove_and_duplicate_keep_original_time(
    market_client,
    buyer_headers,
    order_source,
    saved,
):
    assert saved["listing_visible"]
    assert saved["listing"]["id"] == order_source["listing"]["id"]
    assert saved["listing"]["payload"]["product"]["title"] == "Public loaf"
    assert saved["created_at"].endswith("Z")
    duplicate = save(market_client, buyer_headers, order_source["listing"]["id"])
    assert duplicate.status_code == 200 and duplicate.json() == saved
    assert duplicate.headers["Cache-Control"] == "no-store"
    single = market_client.get(FAVORITES + "/" + saved["id"], headers=buyer_headers)
    assert single.status_code == 200 and single.json() == saved
    page = market_client.get(FAVORITES, headers=buyer_headers)
    assert page.json() == {"items": [saved], "limit": 20, "offset": 0}
    assert page.headers["Cache-Control"] == single.headers["Cache-Control"] == "no-store"
    removed = market_client.delete(FAVORITES + "/" + saved["id"], headers=buyer_headers)
    assert removed.status_code == 204 and removed.content == b""
    assert removed.headers["Cache-Control"] == "no-store"
    assert (
        market_client.delete(FAVORITES + "/" + saved["id"], headers=buyer_headers).status_code
        == 404
    )
    assert market_client.get(FAVORITES, headers=buyer_headers).json()["items"] == []


def test_all_general_accounts_can_save_without_seller_application(
    market_client,
    market_headers,
    buyer_headers,
    market_account,
    order_source,
):
    for headers in (
        buyer_headers,
        market_headers,
        market_account("pending-favorite@example.com", roles=()),
    ):
        assert save(market_client, headers, order_source["listing"]["id"]).status_code == 201
    # Bookmarks are independent of checkout/stock; no seller permission is granted.
    assert market_client.get("/api/v1/auth/me", headers=buyer_headers).json()["roles"] == ["buyer"]


def test_private_owner_scoping_and_missing_ids_are_indistinguishable(
    market_client,
    buyer_headers,
    market_account,
    saved,
):
    other = market_account("different-favorites@example.com", roles=())
    assert market_client.get(FAVORITES, headers=other).json()["items"] == []
    for favorite_id in (saved["id"], str(uuid4())):
        for method in ("get", "delete"):
            response = market_client.request(method, FAVORITES + "/" + favorite_id, headers=other)
            assert response.status_code == 404
            assert response.json()["detail"] == {
                "code": "NOT_FOUND",
                "message": "Resource not found.",
            }
    assert market_client.get(FAVORITES, headers=buyer_headers).json()["items"] == [saved]
    assert market_client.get(FAVORITES).status_code == 401
    assert market_client.get(FAVORITES + "/" + saved["id"]).status_code == 401
    assert (
        market_client.post(FAVORITES, json={"listing_id": saved["listing_id"]}).status_code == 401
    )
    assert market_client.delete(FAVORITES + "/" + saved["id"]).status_code == 401


@pytest.mark.parametrize("change", ["deactivate", "withdraw", "supersede", "seller_role"])
def test_hidden_products_keep_bookmark_without_catalog_data(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    saved,
    change,
):
    if change == "deactivate":
        response = market_client.post(
            order_source["path"] + "/listing/deactivate", headers=market_headers
        )
        assert response.status_code == 204
    elif change == "withdraw":
        url = (
            order_source["draft_url"]
            + "/publications/"
            + order_source["publication"]["id"]
            + "/withdraw"
        )
        assert market_client.post(url, headers=market_headers).status_code == 204
    elif change == "supersede":
        response = market_client.put(
            order_source["draft_url"],
            headers=market_headers,
            json={**order_source["passport_content"], "expected_revision": 1, "price": "19.25"},
        )
        assert response.status_code == 200
        preview = market_client.get(
            order_source["draft_url"] + "/preview", headers=market_headers
        ).json()
        published = market_client.post(
            order_source["draft_url"] + "/publish",
            headers=market_headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        )
        assert published.status_code == 201
    else:
        with Session(market_client.app.state.engine) as db, db.begin():
            db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
    response = market_client.get(FAVORITES + "/" + saved["id"], headers=buyer_headers)
    assert response.status_code == 200
    hidden = response.json()
    assert not hidden["listing_visible"] and hidden["listing"] is None
    assert hidden["id"] == saved["id"] and hidden["created_at"] == saved["created_at"]
    assert "Public loaf" not in response.text and "PRIVATE_MARKET" not in response.text
    assert market_client.get(FAVORITES, headers=buyer_headers).json()["items"] == [hidden]
    assert save(market_client, buyer_headers, saved["listing_id"]).status_code == 404
    assert (
        market_client.delete(FAVORITES + "/" + saved["id"], headers=buyer_headers).status_code
        == 204
    )


def test_public_reactivation_returns_current_card_without_changing_saved_time(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    saved,
):
    path = order_source["path"] + "/listing"
    assert market_client.post(path + "/deactivate", headers=market_headers).status_code == 204
    preview = market_client.get(path + "/preview", headers=market_headers).json()
    assert (
        market_client.post(
            path + "/activate",
            headers=market_headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        ).status_code
        == 200
    )
    row = market_client.get(FAVORITES + "/" + saved["id"], headers=buyer_headers).json()
    assert row["listing_visible"]
    assert row["created_at"] == saved["created_at"]
    assert row["listing"]["published_revision"] != saved["listing"]["published_revision"]


def test_unknown_or_unpublished_listings_are_not_saved(
    market_client,
    market_headers,
    buyer_headers,
    market_record,
    listing,
):
    for listing_id in (str(uuid4()), listing["id"]):
        assert save(market_client, buyer_headers, listing_id).status_code == 404
    with Session(market_client.app.state.engine) as db:
        assert db.scalars(select(Favorite)).all() == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"listing_id": "invalid"},
        {"listing_id": "00000000-0000-4000-8000-000000000001", "account_id": "PRIVATE_MARKER"},
    ],
)
def test_validation_is_strict_and_does_not_echo_private_inputs(market_client, buyer_headers, body):
    response = market_client.post(FAVORITES, headers=buyer_headers, json=body)
    assert response.status_code == 422
    assert "PRIVATE_MARKER" not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_pagination_and_private_fields_do_not_leak(
    market_client,
    buyer_headers,
    order_source,
    saved,
    market_record,
):
    response = market_client.get(FAVORITES + "?limit=1&offset=1", headers=buyer_headers)
    assert response.json() == {"items": [], "limit": 1, "offset": 1}
    # Keep large offsets that SQLite already supports; reject only overflow.
    assert (
        market_client.get(
            FAVORITES + "?offset=3000000000",
            headers=buyer_headers,
        ).status_code
        == 200
    )
    for query in ("limit=0", "limit=101", "offset=-1", "offset=18446744073709551616"):
        assert market_client.get(FAVORITES + "?" + query, headers=buyer_headers).status_code == 422
    content = market_client.get(FAVORITES, headers=buyer_headers).text
    for private in (
        "PRIVATE_MARKET_PRODUCT",
        "PRIVATE_MARKET_RECIPE",
        "account_id",
        market_record["analysis"]["id"],
    ):
        assert private not in content
    assert "reserved" not in content and "on_hand" not in content


def test_concurrent_duplicate_saves_create_one_bookmark(
    market_client,
    buyer_headers,
    order_source,
):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: save(market_client, buyer_headers, order_source["listing"]["id"]),
                range(2),
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 201]
    assert responses[0].json() == responses[1].json()
    assert len(market_client.get(FAVORITES, headers=buyer_headers).json()["items"]) == 1


def test_logout_prevents_further_access(market_client, buyer_headers, saved):
    assert market_client.post("/api/v1/auth/logout", headers=buyer_headers).status_code == 204
    assert market_client.get(FAVORITES, headers=buyer_headers).status_code == 401
    assert (
        market_client.delete(FAVORITES + "/" + saved["id"], headers=buyer_headers).status_code
        == 401
    )


def test_restart_and_migration_preserve_preferences(
    market_client, market_url, buyer_headers, saved
):
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="favorite records"):
        command.downgrade(config, "0012")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(FAVORITES + "/" + saved["id"], headers=buyer_headers).json() == saved
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    market_client.delete(FAVORITES + "/" + saved["id"], headers=buyer_headers)
    command.downgrade(config, "0012")
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get(FAVORITES, headers=buyer_headers).json()["items"] == []


def test_browser_delete_preflight_has_explicit_origin(market_url, monkeypatch):
    monkeypatch.setenv("FAIRMADE_CORS_ORIGINS", "http://localhost:5173")
    with TestClient(create_app(market_url)) as client:
        headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"}
        response = client.options(FAVORITES + "/" + str(uuid4()), headers=headers)
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        assert "DELETE" in response.headers["Access-Control-Allow-Methods"]
        headers["Origin"] = "https://unapproved.example"
        assert client.options(FAVORITES, headers=headers).status_code == 400


def test_openapi_uses_general_account_auth(market_client):
    schema = market_client.get("/openapi.json").json()
    for path in (FAVORITES, FAVORITES + "/{favorite_id}"):
        for operation in schema["paths"][path].values():
            assert operation["security"] == [{"HTTPBearer": []}]
            assert {"401", "404", "422"} <= set(operation["responses"])
    model = schema["components"]["schemas"]["FavoriteCreate"]
    assert model["additionalProperties"] is False
    assert set(model["properties"]) == {"listing_id"}


def test_bookmark_uses_newly_approved_catalog_price(
    market_client,
    market_headers,
    buyer_headers,
    order_source,
    saved,
):
    assert (
        market_client.put(
            order_source["draft_url"],
            headers=market_headers,
            json={**order_source["passport_content"], "expected_revision": 1, "price": "19.25"},
        ).status_code
        == 200
    )
    preview = market_client.get(
        order_source["draft_url"] + "/preview", headers=market_headers
    ).json()
    publication = market_client.post(
        order_source["draft_url"] + "/publish",
        headers=market_headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    ).json()
    path = order_source["path"] + "/listing"
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={
                "expected_revision": 1,
                "passport_publication_id": publication["id"],
                "selling_quantity": {"value": "1", "unit": "item"},
                "seller_display_name": "Updated example bakery",
            },
        ).status_code
        == 200
    )
    preview = market_client.get(path + "/preview", headers=market_headers).json()
    assert (
        market_client.post(
            path + "/activate",
            headers=market_headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        ).status_code
        == 200
    )
    current = market_client.get(FAVORITES + "/" + saved["id"], headers=buyer_headers).json()
    assert current["created_at"] == saved["created_at"]
    assert current["listing"]["payload"]["price"]["amount"] == "19.25"
    assert current["listing"]["payload"]["seller_display_name"] == "Updated example bakery"
