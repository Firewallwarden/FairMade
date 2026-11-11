from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import AssistantConversation, BuyerProfile, LoginSession
from fairmade.personalization.purge import purge

PATH = "/api/v1/buyer/personalization"


def test_explicit_consent_revision_erasure_and_account_isolation(
    market_client, buyer_headers, market_headers
):
    default = market_client.get(PATH, headers=buyer_headers)
    assert default.status_code == 200
    assert default.json()["enabled"] is False and default.json()["revision"] == 0
    assert default.headers["Cache-Control"] == "no-store"
    invalid = {"expected_revision": 0, "enabled": True, "confirmed": False}
    assert market_client.put(PATH, headers=buyer_headers, json=invalid).status_code == 422
    request = {
        **invalid,
        "confirmed": True,
        "preferences": {
            "budget_per_item": "20",
            "location": "PRIVATE_PROFILE_LOCATION",
        },
    }
    saved = market_client.put(PATH, headers=buyer_headers, json=request)
    assert saved.status_code == 200 and saved.json()["enabled"] is True
    assert market_client.put(PATH, headers=buyer_headers, json=request).status_code == 409
    assert market_client.get(PATH, headers=market_headers).json()["revision"] == 0
    erased = market_client.request(
        "DELETE", PATH, headers=buyer_headers, json={"expected_revision": 1}
    )
    assert erased.status_code == 200 and erased.json()["revision"] == 2
    assert erased.json()["preferences"]["budget_per_item"] is None
    with Session(market_client.app.state.engine) as db:
        row = db.scalar(select(BuyerProfile))
        assert row.preferences == {} and row.enabled == 0
    assert (
        market_client.put(
            PATH,
            headers=buyer_headers,
            json={
                **request,
                "expected_revision": 1,
            },
        ).status_code
        == 409
    )  # stale tab cannot restore erased memory


def test_expiry_hides_preferences_and_physical_cleanup_preserves_revision(
    market_client, buyer_headers, enabled_profile
):
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(
            update(BuyerProfile).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
                preferences={"budget_per_item": "9"},
            )
        )
    response = market_client.get(PATH, headers=buyer_headers).json()
    assert response["status"] == "expired" and response["enabled"] is False
    assert response["preferences"]["budget_per_item"] is None
    with Session(market_client.app.state.engine) as db, db.begin():
        assert purge(db) == 1
        row = db.scalar(select(BuyerProfile))
        assert row.preferences == {} and row.revision == 2


def test_remember_proposal_requires_confirmation_and_survives_restart(
    market_client, market_url, buyer_headers, saved_buyer_turn, profile_gateway, order_source
):
    proposed = market_client.post(PATH + "/remember", headers=buyer_headers, json=saved_buyer_turn)
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["preferences"]["budget_per_item"] == "20"
    assert (
        market_client.get(PATH, headers=buyer_headers).json()["preferences"]["budget_per_item"]
        is None
    )
    saved = market_client.put(
        PATH,
        headers=buyer_headers,
        json={
            "expected_revision": proposed.json()["profile_revision"],
            "enabled": True,
            "confirmed": True,
            "preferences": proposed.json()["preferences"],
        },
    )
    assert saved.status_code == 200
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = profile_gateway
        assert (
            restarted.get(PATH, headers=buyer_headers).json()["preferences"]["budget_per_item"]
            == "20"
        )
        follow_up = restarted.post(
            "/api/v1/assistants/conversations/" + saved_buyer_turn["conversation_id"] + "/turns",
            headers=buyer_headers,
            json={
                "request_id": str(uuid4()),
                "expected_revision": 1,
                "question": "Does this fit my remembered budget?",
            },
        )
        assert follow_up.status_code == 200
        assert any("budget is USD 20" in row["text"] for row in follow_up.json()["answer"]["facts"])
        assert follow_up.json()["context_turns"] == 1


@pytest.mark.parametrize(
    "mutation", ["invented_budget", "unsupported_type", "malformed", "duplicate"]
)
def test_model_cannot_invent_remembered_preferences(
    market_client, buyer_headers, saved_buyer_turn, profile_gateway, mutation
):
    profile_gateway.output = {
        "invented_budget": {"budget_per_item": "999", "product_types": []},
        "unsupported_type": {"budget_per_item": None, "product_types": ["eggs"]},
        "malformed": {"role": "seller", "private": "invented"},
        "duplicate": {"budget_per_item": None, "product_types": ["sourdough", "sourdough"]},
    }[mutation]
    assert (
        market_client.post(
            PATH + "/remember", headers=buyer_headers, json=saved_buyer_turn
        ).status_code
        == 502
    )
    assert market_client.get(PATH, headers=buyer_headers).json()["revision"] == 1


def test_other_account_and_seller_conversations_cannot_supply_memory(
    market_client, buyer_headers, market_headers, saved_buyer_turn, profile_gateway, market_record
):
    market_client.put(
        PATH,
        headers=market_headers,
        json={
            "expected_revision": 0,
            "enabled": True,
            "confirmed": True,
        },
    )
    assert (
        market_client.post(
            PATH + "/remember", headers=market_headers, json=saved_buyer_turn
        ).status_code
        == 404
    )
    seller = market_client.post(
        "/api/v1/assistants/conversations",
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {"role": "seller", "product_id": market_record["product"]["id"]},
        },
    ).json()
    assert (
        market_client.post(
            PATH + "/remember",
            headers=market_headers,
            json={"conversation_id": seller["id"], "turn_id": str(uuid4())},
        ).status_code
        == 409
    )
    assert all("PRIVATE_MARKET" not in str(call) for call in profile_gateway.calls)


@pytest.mark.parametrize("action", ["erase", "logout", "delete_chat"])
def test_revocation_during_model_call_discards_proposal(
    market_client, buyer_headers, saved_buyer_turn, profile_gateway, action
):
    def revoke():
        with Session(market_client.app.state.engine) as db, db.begin():
            if action == "erase":
                db.execute(
                    update(BuyerProfile).values(
                        enabled=False, preferences={}, expires_at=None, revision=2
                    )
                )
            elif action == "logout":
                db.execute(delete(LoginSession))
            else:
                db.execute(
                    delete(AssistantConversation).where(
                        AssistantConversation.id == saved_buyer_turn["conversation_id"]
                    )
                )

    profile_gateway.after = revoke
    response = market_client.post(PATH + "/remember", headers=buyer_headers, json=saved_buyer_turn)
    assert response.status_code == {"erase": 409, "logout": 401, "delete_chat": 404}[action]


def test_validation_errors_do_not_echo_private_input(market_client, buyer_headers):
    response = market_client.put(
        PATH,
        headers=buyer_headers,
        json={
            "expected_revision": True,
            "enabled": True,
            "confirmed": True,
            "preferences": {"budget_per_item": 20, "location": "PRIVATE_INVALID_LOCATION"},
        },
    )
    assert response.status_code == 422
    assert "PRIVATE_INVALID_LOCATION" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert market_client.get(PATH).status_code == 401


def test_erasure_removes_profile_derived_answer_copies_but_keeps_original_question(
    market_client, buyer_headers, saved_buyer_turn, profile_gateway, order_source
):
    from fairmade.models import AssistantTurn

    assert (
        market_client.put(
            PATH,
            headers=buyer_headers,
            json={
                "expected_revision": 1,
                "enabled": True,
                "confirmed": True,
                "preferences": {"location": "PRIVATE_REMEMBERED_LOCATION", "budget_per_item": "20"},
            },
        ).status_code
        == 200
    )
    path = "/api/v1/assistants/conversations/" + saved_buyer_turn["conversation_id"] + "/turns"
    response = market_client.post(
        path,
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": 1,
            "question": "Explain my current preferences.",
        },
    )
    assert response.status_code == 200
    with Session(market_client.app.state.engine) as db:
        row = db.get(AssistantTurn, response.json()["id"])
        assert "PRIVATE_REMEMBERED_LOCATION" in str(row.response)
    assert (
        market_client.request(
            "DELETE", PATH, headers=buyer_headers, json={"expected_revision": 2}
        ).status_code
        == 200
    )
    with Session(market_client.app.state.engine) as db:
        row = db.get(AssistantTurn, response.json()["id"])
        assert "PRIVATE_REMEMBERED_LOCATION" not in str(row.response)
        assert row.response["evidence"] == [] and row.response["paragraphs"] == []
        assert row.question == "Explain my current preferences."


def test_profile_erasure_remains_available_at_revision_limit(
    market_client, buyer_headers, enabled_profile
):
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(
            update(BuyerProfile).values(revision=2147483646, preferences={"budget_per_item": "9"})
        )
    response = market_client.request(
        "DELETE", PATH, headers=buyer_headers, json={"expected_revision": 2147483646}
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["preferences"]["budget_per_item"] is None


@pytest.mark.parametrize("text", ["My budget is -$20", "My budget is $-20", "My budget is $20,50"])
def test_unsupported_negative_or_ambiguous_amount_cannot_become_positive_memory(
    market_client, buyer_headers, saved_buyer_turn, profile_gateway, text
):
    from fairmade.models import AssistantTurn

    with Session(market_client.app.state.engine) as db, db.begin():
        db.get(AssistantTurn, saved_buyer_turn["turn_id"]).question = text
    profile_gateway.output = {"budget_per_item": "20", "product_types": []}
    response = market_client.post(PATH + "/remember", headers=buyer_headers, json=saved_buyer_turn)
    assert response.status_code == 502
