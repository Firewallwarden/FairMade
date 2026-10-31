"""Lifecycle, exact approval, privacy boundaries and concurrent publication."""

from concurrent.futures import ThreadPoolExecutor
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
from fairmade.models import AccountRole, PassportDraft, PassportPublication, SellerPricingReview

BACKEND = Path(__file__).parents[2]


def draft_url(source, draft):
    return source["path"] + "/passports/" + draft["id"]


def approval(client, headers, url):
    response = client.get(url + "/preview", headers=headers)
    assert response.status_code == 200, response.text
    checked = response.json()
    return {
        "expected_revision": checked["revision"],
        "preview_hash": checked["preview_hash"],
        "approved": True,
    }


def publish(client, headers, url):
    return client.post(url + "/publish", headers=headers, json=approval(client, headers, url))


def test_draft_preview_exact_publication_and_withdrawal(
    passport_client,
    seller_headers,
    source,
    draft,
):
    url = draft_url(source, draft)
    assert draft["revision"] == 1
    assert passport_client.get("/api/v1/passports/" + draft["id"]).status_code == 404
    preview = passport_client.get(url + "/preview", headers=seller_headers).json()
    response = publish(passport_client, seller_headers, url)
    assert response.status_code == 201, response.text
    published = response.json()
    public_url = "/api/v1/passports/" + published["id"]
    public = passport_client.get(public_url)
    assert public.status_code == 200
    assert public.headers["cache-control"] == "no-store"
    assert set(public.json()) == {"id", "created_at", "payload_hash", "payload"}
    assert public.json()["payload"] == preview["payload"] == published["payload"]
    assert public.json()["payload_hash"] == preview["preview_hash"]
    assert "private-seller@example.com" not in public.text
    assert source["review"]["id"] not in public.text
    assert source["product"]["id"] not in public.text
    assert "PRIVATE_" not in public.text
    with Session(passport_client.app.state.engine) as db:
        row = db.get(PassportPublication, published["id"])
        expected_actor = passport_client.get("/api/v1/auth/me", headers=seller_headers).json()["id"]
        assert row.approved_by_account_id == expected_actor
        assert expected_actor not in public.text
    assert publish(passport_client, seller_headers, url).status_code == 200
    history = passport_client.get(url + "/publications", headers=seller_headers).json()
    assert len(history["items"]) == 1
    withdrawal = url + "/publications/" + published["id"] + "/withdraw"
    assert passport_client.post(withdrawal, headers=seller_headers).status_code == 204
    assert passport_client.post(withdrawal, headers=seller_headers).status_code == 204
    assert passport_client.get(public_url).status_code == 404
    assert passport_client.get(public_url).headers["cache-control"] == "no-store"
    assert publish(passport_client, seller_headers, url).status_code == 409
    history = passport_client.get(url + "/publications", headers=seller_headers).json()
    assert history["items"][0]["state"] == "withdrawn"
    assert history["items"][0]["withdrawn_at"].endswith("Z")


def test_private_edits_require_new_preview_approval_and_supersede_previous(
    passport_client,
    seller_headers,
    source,
    draft,
):
    url = draft_url(source, draft)
    first = publish(passport_client, seller_headers, url).json()
    old_approval = approval(passport_client, seller_headers, url)
    changed = {
        **draft["content"],
        "expected_revision": 1,
        "price": "19.00",
        "disclosures": {"cost_categories": ["materials"]},
    }
    updated = passport_client.put(url, headers=seller_headers, json=changed)
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    # Draft edits are private, so the already approved snapshot is untouched.
    assert (
        passport_client.get("/api/v1/passports/" + first["id"]).json()["payload"]["price"]["amount"]
        == "17.00"
    )
    assert (
        passport_client.post(
            url + "/publish", headers=seller_headers, json=old_approval
        ).status_code
        == 409
    )
    assert passport_client.put(url, headers=seller_headers, json=changed).status_code == 409
    second = publish(passport_client, seller_headers, url)
    assert second.status_code == 201
    public = passport_client.get("/api/v1/passports/" + second.json()["id"]).json()
    assert public["payload"]["price"]["amount"] == "19.00"
    assert public["payload"]["costs"]["category_costs_per_unit"] == {"materials": "5.000000"}
    assert passport_client.get("/api/v1/passports/" + first["id"]).status_code == 404
    assert "PRIVATE_INGREDIENT_NAME" not in str(public)
    assert (
        passport_client.get(url + "/publications", headers=seller_headers).json()["items"][1][
            "state"
        ]
        == "superseded"
    )


def test_wrong_hash_never_publishes(passport_client, seller_headers, source, draft):
    url = draft_url(source, draft)
    body = approval(passport_client, seller_headers, url)
    body["preview_hash"] = "0" * 64
    response = passport_client.post(url + "/publish", headers=seller_headers, json=body)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PREVIEW_MISMATCH"
    with Session(passport_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(PassportPublication)) == 0


def private_routes(source, draft, content):
    url = draft_url(source, draft)
    return [
        ("post", source["path"] + "/passports", content),
        ("get", source["path"] + "/passports", None),
        ("get", url, None),
        ("put", url, {**content, "expected_revision": 1}),
        ("get", url + "/preview", None),
        (
            "post",
            url + "/publish",
            {"expected_revision": 1, "preview_hash": "0" * 64, "approved": True},
        ),
        ("get", url + "/publications", None),
        ("post", url + "/publications/" + str(uuid4()) + "/withdraw", None),
    ]


@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic invalid"])
def test_private_routes_require_auth(passport_client, source, draft, content, authorization):
    headers = {"Authorization": authorization} if authorization else {}
    for method, url, body in private_routes(source, draft, content):
        assert passport_client.request(method, url, headers=headers, json=body).status_code == 401


@pytest.mark.parametrize("roles,pending", [((), False), ((), True), (("admin",), False)])
def test_buyers_pending_and_admin_only_cannot_manage_disclosures(
    passport_client,
    source,
    draft,
    content,
    account_factory,
    roles,
    pending,
):
    headers = account_factory("buyer@example.com", roles)
    if pending:
        assert (
            passport_client.post(
                "/api/v1/seller-applications", headers=headers, json={}
            ).status_code
            == 201
        )
    for method, url, body in private_routes(source, draft, content):
        assert passport_client.request(method, url, headers=headers, json=body).status_code == 403


def test_cross_seller_and_product_isolation(
    passport_client,
    seller_headers,
    source,
    draft,
    content,
    account_factory,
):
    other = account_factory("other@example.com", ("seller",))
    for method, url, body in private_routes(source, draft, content):
        assert passport_client.request(method, url, headers=other, json=body).status_code == 404
    product = passport_client.post(
        "/api/v1/products",
        headers=seller_headers,
        json={
            "name": "Other loaf",
            "product_type": "sourdough",
            "selling_unit": "loaf",
        },
    ).json()
    path = "/api/v1/products/" + product["id"] + "/passports"
    assert passport_client.post(path, headers=seller_headers, json=content).status_code == 404
    assert passport_client.get(path + "/" + draft["id"], headers=seller_headers).status_code == 404


def test_source_version_is_checked_without_leaking_source(
    passport_client, seller_headers, source, draft
):
    with Session(passport_client.app.state.engine) as db, db.begin():
        db.get(SellerPricingReview, source["review"]["id"]).review_version = "future-version"
    url = draft_url(source, draft)
    response = passport_client.get(url + "/preview", headers=seller_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "UNSUPPORTED_REVIEW_VERSION"


def test_seller_role_loss_hides_publication(passport_client, seller_headers, source, draft):
    published = publish(passport_client, seller_headers, draft_url(source, draft)).json()
    account_id = passport_client.get("/api/v1/auth/me", headers=seller_headers).json()["id"]
    with Session(passport_client.app.state.engine) as db, db.begin():
        db.delete(db.get(AccountRole, (account_id, "seller")))
    assert passport_client.get("/api/v1/passports/" + published["id"]).status_code == 404


def test_pagination_and_restart(passport_client, seller_headers, source, draft, passport_url):
    url = draft_url(source, draft)
    published = publish(passport_client, seller_headers, url).json()
    with TestClient(create_app(passport_url)) as restarted:
        assert (
            restarted.get("/api/v1/passports/" + published["id"]).json()["payload"]
            == published["payload"]
        )
    for path in (source["path"] + "/passports", url + "/publications"):
        page = passport_client.get(path + "?limit=1&offset=0", headers=seller_headers).json()
        assert page["limit"] == 1 and len(page["items"]) == 1
        assert passport_client.get(path + "?offset=1", headers=seller_headers).json()["items"] == []
        for query in ("?limit=0", "?limit=101", "?offset=-1"):
            assert passport_client.get(path + query, headers=seller_headers).status_code == 422


def test_concurrent_approval_is_idempotent(
    passport_client, seller_headers, source, draft, passport_url
):
    url = draft_url(source, draft)
    body = approval(passport_client, seller_headers, url)
    barrier = Barrier(2)

    def submit(_index):
        with TestClient(create_app(passport_url)) as client:
            barrier.wait(timeout=10)
            return client.post(url + "/publish", headers=seller_headers, json=body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    with Session(passport_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(PassportPublication)) == 1


def test_competing_drafts_leave_one_active_publication(
    passport_client,
    seller_headers,
    source,
    draft,
    content,
    passport_url,
):
    second = passport_client.post(
        source["path"] + "/passports",
        headers=seller_headers,
        json={**content, "title": "Another title"},
    ).json()
    urls = [draft_url(source, item) for item in (draft, second)]
    bodies = [approval(passport_client, seller_headers, url) for url in urls]
    barrier = Barrier(2)

    def submit(index):
        with TestClient(create_app(passport_url)) as client:
            barrier.wait(timeout=10)
            return client.post(urls[index] + "/publish", headers=seller_headers, json=bodies[index])

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, range(2)))
    assert all(response.status_code == 201 for response in responses)
    statuses = [
        passport_client.get("/api/v1/passports/" + response.json()["id"]).status_code
        for response in responses
    ]
    assert sorted(statuses) == [200, 404]


@pytest.mark.parametrize("operation", ["create", "replace", "publish", "withdraw"])
def test_transaction_failures_do_not_change_visibility(
    passport_client,
    seller_headers,
    source,
    draft,
    content,
    passport_url,
    operation,
):
    url = draft_url(source, draft)
    original = publish(passport_client, seller_headers, url).json()
    body = approval(passport_client, seller_headers, url)
    if operation == "publish":
        updated = passport_client.put(
            url, headers=seller_headers, json={**content, "expected_revision": 1, "price": "20"}
        )
        assert updated.status_code == 200
        body = approval(passport_client, seller_headers, url)

    def fail_commit(_db):
        raise RuntimeError("Synthetic Passport storage failure")

    event.listen(Session, "before_commit", fail_commit)
    try:
        with TestClient(create_app(passport_url), raise_server_exceptions=False) as failing:
            if operation == "create":
                response = failing.post(
                    source["path"] + "/passports", headers=seller_headers, json=content
                )
            elif operation == "replace":
                response = failing.put(
                    url,
                    headers=seller_headers,
                    json={**content, "expected_revision": 1, "price": "20"},
                )
            elif operation == "publish":
                response = failing.post(url + "/publish", headers=seller_headers, json=body)
            else:
                response = failing.post(
                    url + "/publications/" + original["id"] + "/withdraw", headers=seller_headers
                )
            assert response.status_code == 500
    finally:
        event.remove(Session, "before_commit", fail_commit)
    public = passport_client.get("/api/v1/passports/" + original["id"])
    assert public.status_code == 200 and public.json()["payload"] == original["payload"]
    with Session(passport_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(PassportDraft)) == 1
        assert db.scalar(select(func.count()).select_from(PassportPublication)) == 1


def test_migrations_preserve_all_private_sources(passport_client, seller_headers, source, draft):
    engine = passport_client.app.state.engine
    tables = (
        "products",
        "accounts",
        "account_roles",
        "analyses",
        "seller_pricing_reviews",
        "quality_lock_sets",
        "quality_evaluations",
        "price_observations",
        "price_comparisons",
    )

    def before_rows():
        with engine.connect() as connection:
            return {
                table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
                for table in tables
            }

    before = before_rows()
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    command.downgrade(config, "0005")
    assert before_rows() == before
    command.upgrade(config, "head")
    assert before_rows() == before
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_openapi_distinguishes_public_and_private(passport_client):
    schema = passport_client.get("/openapi.json").json()
    public = schema["paths"]["/api/v1/passports/{publication_id}"]["get"]
    assert not public.get("security")
    private = schema["paths"]["/api/v1/products/{product_id}/passports/{draft_id}/publish"]["post"]
    assert private["security"] == [{"HTTPBearer": []}]
    assert {"200", "201", "401", "403", "404", "409", "422"} <= set(private["responses"])
