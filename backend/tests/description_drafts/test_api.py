import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AccountRole, DescriptionDraft, LoginSession


def make(client, headers, path, body=None):
    return client.post(path, headers=headers, json=body or {"request_id": str(uuid4())})


def approval(draft):
    return {
        "expected_revision": draft["revision"],
        "preview_hash": draft["preview_hash"],
        "approved": True,
    }


def test_generation_is_private_scoped_and_does_not_modify_product_or_public_snapshot(
    market_client,
    market_headers,
    market_record,
    listing,
    description_path,
    description_gateway,
):
    listing_path = market_record["path"] + "/listing"
    preview = market_client.get(listing_path + "/preview", headers=market_headers).json()
    assert (
        market_client.post(
            listing_path + "/activate", headers=market_headers, json=approval(preview)
        ).status_code
        == 200
    )
    public_path = "/api/v1/marketplace/listings/" + listing["id"]
    public_before = market_client.get(public_path).json()
    original = market_client.get(market_record["path"], headers=market_headers).json()[
        "description"
    ]
    response = make(market_client, market_headers, description_path)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["state"] == "draft" and draft["revision"] == 1
    assert draft["generated_text"] == draft["description"]
    assert response.headers["Cache-Control"] == "no-store" and draft["notices"]
    prompt = json.dumps(description_gateway.calls)
    assert "PRIVATE_MARKET_RECIPE" not in prompt and "PRIVATE_MARKET_WORKER" not in prompt
    assert (
        market_client.get(market_record["path"], headers=market_headers).json()["description"]
        == original
    )
    applied = market_client.post(
        description_path + "/" + draft["id"] + "/approve",
        headers=market_headers,
        json=approval(draft),
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["state"] == "approved"
    assert (
        market_client.get(market_record["path"], headers=market_headers).json()["description"]
        == draft["description"]
    )
    assert market_client.get(public_path).json() == public_before


def test_safe_retries_conflicting_requests_and_edit_review_hashes(
    market_client,
    market_headers,
    market_record,
    description_path,
    description_gateway,
):
    body = {"request_id": str(uuid4()), "tone": "plain"}
    draft = make(market_client, market_headers, description_path, body).json()
    assert make(market_client, market_headers, description_path, body).json()["id"] == draft["id"]
    assert len(description_gateway.calls) == 1
    assert (
        make(
            market_client,
            market_headers,
            description_path,
            {
                **body,
                "tone": "friendly",
            },
        ).status_code
        == 409
    )
    path = description_path + "/" + draft["id"]
    edited = market_client.put(
        path,
        headers=market_headers,
        json={
            "expected_revision": 1,
            "description": "Seller-reviewed wording for this loaf.",
        },
    )
    assert edited.status_code == 200
    assert edited.json()["generated_text"] == draft["generated_text"]
    assert edited.json()["preview_hash"] != draft["preview_hash"]
    assert (
        market_client.post(
            path + "/approve", headers=market_headers, json=approval(draft)
        ).status_code
        == 409
    )
    assert (
        market_client.post(
            path + "/approve", headers=market_headers, json=approval(edited.json())
        ).status_code
        == 200
    )
    # Later manual editing must survive an exact approval retry.
    assert (
        market_client.patch(
            market_record["path"],
            headers=market_headers,
            json={"description": "A later deliberate seller edit."},
        ).status_code
        == 200
    )
    assert (
        market_client.post(
            path + "/approve", headers=market_headers, json=approval(edited.json())
        ).status_code
        == 200
    )
    assert (
        market_client.get(market_record["path"], headers=market_headers).json()["description"]
        == "A later deliberate seller edit."
    )
    assert (
        market_client.put(
            path,
            headers=market_headers,
            json={
                "expected_revision": 2,
                "description": "Cannot edit approved history.",
            },
        ).status_code
        == 409
    )


def test_source_changes_require_new_generation(
    market_client,
    market_headers,
    market_record,
    description_path,
    description_gateway,
):
    draft = make(market_client, market_headers, description_path).json()
    assert (
        market_client.patch(
            market_record["path"], headers=market_headers, json={"name": "A renamed product"}
        ).status_code
        == 200
    )
    response = market_client.post(
        description_path + "/" + draft["id"] + "/approve",
        headers=market_headers,
        json=approval(draft),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DESCRIPTION_SOURCE_CHANGED"


@pytest.mark.parametrize("change", ["product", "session", "role"])
def test_mid_generation_changes_or_revocation_leave_no_draft(
    market_client,
    market_headers,
    market_record,
    description_path,
    description_gateway,
    change,
):
    def modify():
        if change == "product":
            market_client.patch(
                market_record["path"],
                headers=market_headers,
                json={"name": "Changed during generation"},
            )
        else:
            with Session(market_client.app.state.engine) as db, db.begin():
                db.execute(delete(LoginSession if change == "session" else AccountRole))

    description_gateway.after = modify
    response = make(market_client, market_headers, description_path)
    assert response.status_code == {"product": 409, "session": 401, "role": 403}[change]
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(DescriptionDraft)) == 0


def test_only_verified_owner_can_generate_or_read(
    market_client,
    market_headers,
    market_account,
    description_path,
    description_gateway,
):
    assert (
        market_client.post(description_path, json={"request_id": str(uuid4())}).status_code == 401
    )
    buyer = market_account("description-buyer@example.com", roles=())
    assert make(market_client, buyer, description_path).status_code == 403
    other = market_account("description-other@example.com")
    assert make(market_client, other, description_path).status_code == 404
    assert description_gateway.calls == []
    draft = make(market_client, market_headers, description_path).json()
    assert market_client.get(description_path + "/" + draft["id"], headers=other).status_code == 404
    assert market_client.get(description_path, headers=buyer).status_code == 403


@pytest.mark.parametrize(
    "output",
    [
        {"description": ""},
        {"description": "x" * 2001},
        {"description": "Costs $987654.23."},
        {"description": "Certified organic sourdough."},
        {"description": "<script>alert()</script>"},
        {"description": "Visit https://external.invalid"},
        {"description": "Bread.", "publish": True},
    ],
)
def test_invalid_or_unsupported_model_copy_fails_closed(
    market_client,
    market_headers,
    description_path,
    description_gateway,
    output,
):
    description_gateway.output = output
    response = make(market_client, market_headers, description_path)
    assert response.status_code == 502 and response.headers["Cache-Control"] == "no-store"
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(DescriptionDraft)) == 0


def test_provider_failure_releases_slot_and_allows_safe_retry(
    market_client,
    market_headers,
    description_path,
    description_gateway,
):
    body = {"request_id": str(uuid4())}
    description_gateway.error = HTTPException(503, detail={"code": "ASSISTANT_UNAVAILABLE"})
    assert make(market_client, market_headers, description_path, body).status_code == 503
    description_gateway.error = None
    assert make(market_client, market_headers, description_path, body).status_code == 201


def test_explicit_approval_input_validation_and_restart(
    market_client,
    market_headers,
    description_path,
    description_gateway,
    market_url,
):
    draft = make(market_client, market_headers, description_path).json()
    path = description_path + "/" + draft["id"]
    denied = market_client.post(
        path + "/approve",
        headers=market_headers,
        json={
            **approval(draft),
            "approved": False,
        },
    )
    assert denied.status_code == 422 and denied.headers["Cache-Control"] == "no-store"
    assert (
        market_client.post(
            path + "/approve", headers=market_headers, json=approval(draft)
        ).status_code
        == 200
    )
    with TestClient(create_app(market_url)) as restarted:
        response = restarted.get(path, headers=market_headers)
        assert response.status_code == 200
        assert datetime.fromisoformat(response.json()["approved_at"]).utcoffset() == timedelta(0)
        assert response.json()["preview_hash"] == draft["preview_hash"]


def test_invalid_request_fields_do_not_echo_raw_inputs(
    market_client,
    market_headers,
    description_path,
    description_gateway,
):
    response = make(
        market_client,
        market_headers,
        description_path,
        {
            "request_id": str(uuid4()),
            "system_prompt": "PRIVATE_RAW_INSTRUCTION",
        },
    )
    assert response.status_code == 422 and "PRIVATE_RAW" not in response.text
    assert description_gateway.calls == []


def test_approval_failure_rolls_back_both_product_and_audit(
    market_client,
    market_headers,
    market_record,
    description_path,
    description_gateway,
    market_url,
):
    draft = make(market_client, market_headers, description_path).json()
    original = market_client.get(market_record["path"], headers=market_headers).json()[
        "description"
    ]

    def fail(db):
        if any(isinstance(row, DescriptionDraft) and row.state == "approved" for row in db.dirty):
            raise RuntimeError("Synthetic approval failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            result = client.post(
                description_path + "/" + draft["id"] + "/approve",
                headers=market_headers,
                json=approval(draft),
            )
            assert result.status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert (
        market_client.get(market_record["path"], headers=market_headers).json()["description"]
        == original
    )
    assert (
        market_client.get(description_path + "/" + draft["id"], headers=market_headers).json()[
            "state"
        ]
        == "draft"
    )


def test_description_and_assistant_share_the_same_gpu_slot(
    market_client,
    market_headers,
    description_path,
    description_gateway,
):
    from fairmade.assistants.runtime import INFERENCE_SLOT

    assert INFERENCE_SLOT.acquire(blocking=False)
    try:
        assert make(market_client, market_headers, description_path).status_code == 429
        assert description_gateway.calls == []
    finally:
        INFERENCE_SLOT.release()
