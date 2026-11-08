"""Photo ownership, listing approval, visibility, atomic storage and quotas."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AccountRole, ListingPhoto, MarketplaceListing, ProductPhoto
from fairmade.photos import processing, repository

BACKEND = Path(__file__).parents[2]
PUBLIC = "/api/v1/marketplace/photos/"


@pytest.fixture
def image_bytes():
    output = BytesIO()
    Image.new("RGB", (32, 24), "blue").save(output, format="PNG")
    return output.getvalue()


def upload(client, headers, path, data):
    return client.post(
        path + "/photos", headers={**headers, "Content-Type": "image/png"}, content=data
    )


def activate(client, headers, path):
    preview = client.get(path + "/listing/preview", headers=headers)
    assert preview.status_code == 200, preview.text
    checked = preview.json()
    return client.post(
        path + "/listing/activate",
        headers=headers,
        json={
            "expected_revision": checked["revision"],
            "preview_hash": checked["preview_hash"],
            "approved": True,
        },
    )


def replace(client, headers, path, content, revision, photos):
    return client.put(
        path + "/listing",
        headers=headers,
        json={
            **content,
            "expected_revision": revision,
            "photos": photos,
        },
    )


@pytest.fixture
def photo(market_client, market_headers, market_record, image_bytes):
    response = upload(market_client, market_headers, market_record["path"], image_bytes)
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_metadata_is_private_and_normalized_bytes_are_owner_only(
    market_client,
    market_headers,
    market_record,
    photo,
):
    assert (photo["width"], photo["height"]) == (32, 24)
    assert photo["media_type"] == "image/jpeg" and photo["created_at"].endswith("Z")
    assert "image_bytes" not in photo and "src" not in photo
    path = market_record["path"] + "/photos"
    listing = market_client.get(path, headers=market_headers)
    assert listing.json()["items"] == [photo]
    assert listing.headers["Cache-Control"] == "no-store"
    content = market_client.get(path + "/" + photo["id"] + "/content", headers=market_headers)
    assert content.status_code == 200 and content.headers["Content-Type"] == "image/jpeg"
    assert content.headers["X-Content-Type-Options"] == "nosniff"
    assert content.headers["Cache-Control"] == "no-store"
    assert market_client.get(PUBLIC + photo["id"]).status_code == 404


def test_exact_listing_approval_publishes_immutable_selected_photo_and_alt_text(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
    photo,
):
    path = market_record["path"]
    selection = [{"photo_id": photo["id"], "alt_text": "Synthetic loaf photo"}]
    assert (
        replace(market_client, market_headers, path, listing_content, 1, selection).status_code
        == 200
    )
    assert market_client.get(PUBLIC + photo["id"]).status_code == 404
    assert activate(market_client, market_headers, path).status_code == 200
    public = market_client.get("/api/v1/marketplace/listings/" + listing["id"]).json()
    approved = public["payload"]["photos"][0]
    assert approved["id"] == photo["id"] and approved["sha256"] == photo["sha256"]
    assert (
        approved["alt_text"] == "Synthetic loaf photo" and approved["src"] == PUBLIC + photo["id"]
    )
    assert "product_id" not in approved and "created_at" not in approved
    image = market_client.get(approved["src"])
    assert image.status_code == 200
    assert image.headers["Cache-Control"] == "no-store"
    assert replace(market_client, market_headers, path, listing_content, 2, []).status_code == 200
    assert market_client.get(PUBLIC + photo["id"]).status_code == 200
    assert activate(market_client, market_headers, path).status_code == 200
    assert market_client.get(PUBLIC + photo["id"]).status_code == 404
    assert (
        market_client.delete(path + "/photos/" + photo["id"], headers=market_headers).status_code
        == 204
    )


def test_active_and_draft_references_block_deletion(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
    photo,
):
    path = market_record["path"]
    photo_path = path + "/photos/" + photo["id"]
    assert (
        replace(
            market_client,
            market_headers,
            path,
            listing_content,
            1,
            [{"photo_id": photo["id"], "alt_text": "Example"}],
        ).status_code
        == 200
    )
    assert (
        market_client.delete(photo_path, headers=market_headers).json()["detail"]["code"]
        == "PHOTO_IN_USE"
    )
    assert activate(market_client, market_headers, path).status_code == 200
    assert replace(market_client, market_headers, path, listing_content, 2, []).status_code == 200
    assert market_client.delete(photo_path, headers=market_headers).status_code == 409
    market_client.post(path + "/listing/deactivate", headers=market_headers)
    assert market_client.get(PUBLIC + photo["id"]).status_code == 404
    assert market_client.delete(photo_path, headers=market_headers).status_code == 204
    assert market_client.get(photo_path + "/content", headers=market_headers).status_code == 404


def test_foreign_product_and_photo_ids_cannot_be_uploaded_read_selected_or_deleted(
    market_client,
    market_headers,
    market_account,
    market_record,
    listing,
    listing_content,
    photo,
    image_bytes,
):
    other = market_account("other-photo-owner@example.com")
    path = market_record["path"]
    for response in (
        upload(market_client, other, path, image_bytes),
        market_client.get(path + "/photos", headers=other),
        market_client.get(path + "/photos/" + photo["id"] + "/content", headers=other),
        market_client.delete(path + "/photos/" + photo["id"], headers=other),
    ):
        assert response.status_code == 404
    product = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={"name": "Second", "product_type": "other", "selling_unit": "item"},
    ).json()
    assert (
        market_client.get(
            "/api/v1/products/" + product["id"] + "/photos/" + photo["id"] + "/content",
            headers=market_headers,
        ).status_code
        == 404
    )
    response = replace(
        market_client,
        market_headers,
        path,
        listing_content,
        1,
        [{"photo_id": str(uuid4()), "alt_text": "Missing"}],
    )
    assert response.status_code == 404


def test_buyer_cannot_upload_and_no_auth_is_rejected_before_image_parsing(
    market_client,
    buyer_headers,
    market_record,
):
    path = market_record["path"]
    assert upload(market_client, {}, path, b"INVALID").status_code == 401
    assert upload(market_client, buyer_headers, path, b"INVALID").status_code == 403


@pytest.mark.parametrize("media_type", ["image/svg+xml", "text/html", "application/octet-stream"])
def test_unsupported_content_types_are_rejected_without_echoing(
    market_client,
    market_headers,
    market_record,
    media_type,
):
    response = market_client.post(
        market_record["path"] + "/photos",
        headers={
            **market_headers,
            "Content-Type": media_type,
        },
        content=b"PRIVATE_UNTRUSTED_BODY",
    )
    assert response.status_code == 415
    assert "PRIVATE_UNTRUSTED" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


def test_stream_limit_and_product_quota_are_enforced_atomically(
    market_client,
    market_headers,
    market_record,
    image_bytes,
    monkeypatch,
):
    monkeypatch.setattr(processing, "MAX_UPLOAD_BYTES", 10)
    assert (
        upload(market_client, market_headers, market_record["path"], image_bytes).status_code == 413
    )
    monkeypatch.setattr(processing, "MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
    monkeypatch.setattr(repository, "MAX_PRODUCT_PHOTOS", 1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: upload(market_client, market_headers, market_record["path"], image_bytes),
                range(2),
            )
        )
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert (
        len(
            market_client.get(market_record["path"] + "/photos", headers=market_headers).json()[
                "items"
            ]
        )
        == 1
    )


def test_failed_upload_commit_persists_neither_metadata_nor_blob(
    market_client,
    market_headers,
    market_record,
    market_url,
    image_bytes,
):
    def fail(db):
        if any(isinstance(item, ProductPhoto) for item in db.new):
            raise RuntimeError("Synthetic storage failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert (
                upload(client, market_headers, market_record["path"], image_bytes).status_code
                == 500
            )
    finally:
        event.remove(Session, "before_commit", fail)
    with Session(market_client.app.state.engine) as db:
        assert db.scalars(select(ProductPhoto)).all() == []


@pytest.mark.parametrize("reason", ["passport", "role"])
def test_public_visibility_tracks_passport_withdrawal_and_role_loss(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
    photo,
    reason,
):
    path = market_record["path"]
    assert (
        replace(
            market_client,
            market_headers,
            path,
            listing_content,
            1,
            [{"photo_id": photo["id"], "alt_text": "Example"}],
        ).status_code
        == 200
    )
    assert activate(market_client, market_headers, path).status_code == 200
    assert market_client.get(PUBLIC + photo["id"]).status_code == 200
    if reason == "role":
        with Session(market_client.app.state.engine) as db, db.begin():
            db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
    else:
        response = market_client.post(
            market_record["draft_url"]
            + "/publications/"
            + market_record["publication"]["id"]
            + "/withdraw",
            headers=market_headers,
        )
        assert response.status_code == 204
    assert market_client.get(PUBLIC + photo["id"]).status_code == 404


def test_photo_migration_restart_metadata_and_downgrade_guard_preserve_bytes(
    market_client,
    market_headers,
    market_record,
    photo,
    market_url,
):
    path = market_record["path"] + "/photos/" + photo["id"] + "/content"
    expected = market_client.get(path, headers=market_headers).content
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="photo records"):
        command.downgrade(config, "0015")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(path, headers=market_headers).content == expected
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_listing_photo_selection_bounds_and_duplicates_reject_invalid_body(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
    photo,
):
    selection = {"photo_id": photo["id"], "alt_text": "Example"}
    for photos in ([selection, selection], [selection] * 7, [{**selection, "alt_text": " "}]):
        assert (
            replace(
                market_client, market_headers, market_record["path"], listing_content, 1, photos
            ).status_code
            == 422
        )


def test_photo_openapi_uses_raw_binary_upload_and_anonymous_public_reads(market_client):
    schema = market_client.get("/openapi.json").json()
    upload_path = "/api/v1/products/{product_id}/photos"
    operation = schema["paths"][upload_path]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert set(operation["requestBody"]["content"]) == {"image/png", "image/jpeg"}
    assert "security" not in schema["paths"][PUBLIC + "{photo_id}"]["get"]


def test_failed_activation_rolls_back_public_references_with_listing_payload(
    market_client,
    market_headers,
    market_record,
    listing,
    listing_content,
    photo,
    market_url,
):
    path = market_record["path"]
    assert (
        replace(
            market_client,
            market_headers,
            path,
            listing_content,
            1,
            [{"photo_id": photo["id"], "alt_text": "Example"}],
        ).status_code
        == 200
    )

    def fail(db):
        if any(isinstance(row, MarketplaceListing) and row.state == "active" for row in db.dirty):
            raise RuntimeError("Synthetic activation failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert activate(client, market_headers, path).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert market_client.get(PUBLIC + photo["id"]).status_code == 404
    with Session(market_client.app.state.engine) as db:
        assert db.scalars(select(ListingPhoto)).all() == []
        assert db.get(ProductPhoto, photo["id"]) is not None


def test_account_storage_quota_applies_across_products(
    market_client,
    market_headers,
    market_record,
    photo,
    image_bytes,
    monkeypatch,
):
    monkeypatch.setattr(repository, "MAX_ACCOUNT_BYTES", photo["byte_count"])
    product = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={
            "name": "Another product",
            "product_type": "other",
            "selling_unit": "item",
        },
    ).json()
    response = upload(
        market_client, market_headers, "/api/v1/products/" + product["id"], image_bytes
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PHOTO_STORAGE_LIMIT"


def test_corrupt_stored_bytes_fail_closed_without_serving_unapproved_content(
    market_client,
    market_headers,
    market_record,
    photo,
):
    with market_client.app.state.engine.begin() as connection:
        connection.execute(
            text("UPDATE product_photos SET image_bytes = :data WHERE id = :id"),
            {"data": b"x" * photo["byte_count"], "id": photo["id"]},
        )
    response = market_client.get(
        market_record["path"] + "/photos/" + photo["id"] + "/content", headers=market_headers
    )
    assert response.status_code == 503 and response.json()["detail"]["code"] == "PHOTO_UNAVAILABLE"
    assert response.headers["Cache-Control"] == "no-store"
