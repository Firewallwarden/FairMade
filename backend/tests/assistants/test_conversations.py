"""Persisted dialogue continuity, current evidence, ownership, and atomic writes."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from fairmade.assistants.dialogue import Dialogue, PriorTurn
from fairmade.conversations import repository
from fairmade.conversations import service as conversation_service
from fairmade.main import create_app
from fairmade.models import (
    AccountRole,
    AssistantConversation,
    AssistantTurn,
    LoginSession,
    Product,
)

PATH = "/api/v1/assistants/conversations"


@pytest.fixture
def conversation(market_client, market_headers, seller_question):
    response = market_client.post(
        PATH,
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {"role": "seller", "product_id": seller_question["product_id"]},
        },
    )
    assert response.status_code == 201
    return response.json()


def ask(client, headers, conversation, question="Explain my costs.", revision=0, request_id=None):
    return client.post(
        PATH + "/" + conversation["id"] + "/turns",
        headers=headers,
        json={
            "request_id": request_id or str(uuid4()),
            "expected_revision": revision,
            "question": question,
        },
    )


def turns(client, headers, conversation):
    return client.get(PATH + "/" + conversation["id"] + "/turns", headers=headers)


def test_saved_price_follow_up_and_restart(
    market_client, market_url, market_headers, conversation, ai_gateway
):
    ai_gateway.prices = ["8"]
    first = ask(market_client, market_headers, conversation, "What if I charge $8?")
    assert first.status_code == 200
    assert first.json()["context_turns"] == 0
    original = first.json()["answer"]["evidence"][-1]["data"]["scenarios"]
    ai_gateway.prices = []
    ai_gateway.calls.clear()
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = ai_gateway
        second = ask(
            restarted, market_headers, conversation, "Why does that price lose money?", revision=1
        )
        assert second.status_code == 200
        assert second.json()["context_turns"] == 1
        assert second.json()["revision"] == 2
        assert second.json()["answer"]["evidence"][-1]["data"]["scenarios"] == original
        assert "Earlier proposed prices" in second.json()["answer"]["notices"][-1]
        history = turns(restarted, market_headers, conversation)
        assert [row["revision"] for row in history.json()["items"]] == [1, 2]
        assert all(row["answer_status"] == "available" for row in history.json()["items"])
    messages = ai_gateway.calls[-1]["messages"]
    assert messages[1]["role"] == "user"
    assert "[prior proposed value]" in messages[1]["content"]
    assert "The selected evidence" in messages[2]["content"]
    assert "$8" not in json.dumps(messages)


def test_new_explicit_price_replaces_retained_price(
    market_client, market_headers, conversation, ai_gateway
):
    ai_gateway.prices = ["8"]
    assert ask(market_client, market_headers, conversation, "Charge $8?").status_code == 200
    ai_gateway.prices = ["12.5"]
    response = ask(market_client, market_headers, conversation, "What about $12.5?", revision=1)
    assert response.status_code == 200
    assert Decimal(response.json()["answer"]["evidence"][-1]["data"]["scenarios"][0]["price"]) == (
        Decimal("12.5")
    )
    # Old prose about an earlier price must not become the new scenario's answer.
    prompt = ai_gateway.calls[-1]["messages"]
    assert prompt[1]["role"] == "user"
    assert prompt[2]["role"] == "user"


def test_new_numeric_question_cannot_silently_reuse_old_price(
    market_client, market_headers, conversation, ai_gateway
):
    ai_gateway.prices = ["8"]
    assert ask(market_client, market_headers, conversation, "Charge $8?").status_code == 200
    ai_gateway.prices = []
    response = ask(
        market_client, market_headers, conversation, "Why does $9 work differently?", revision=1
    )
    assert response.status_code == 200
    assert not any(
        row["title"] == "Deterministic requested price scenarios"
        for row in response.json()["answer"]["evidence"]
    )


def test_changed_selling_basis_requires_an_explicit_new_price(
    market_client, market_headers, market_record, conversation, ai_gateway, payload
):
    ai_gateway.prices = ["8"]
    assert ask(market_client, market_headers, conversation, "Charge $8?").status_code == 200
    edited = market_client.patch(
        market_record["path"], headers=market_headers, json={"selling_unit": "two loaves"}
    )
    assert edited.status_code == 200
    assert (
        market_client.post(
            market_record["path"] + "/analyses", headers=market_headers, json=payload
        ).status_code
        == 201
    )
    ai_gateway.prices = []
    response = ask(market_client, market_headers, conversation, "Why that price?", revision=1)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONVERSATION_PRICE_BASIS_CHANGED"


def test_follow_up_recalculates_against_latest_analysis_and_hides_stale_answers(
    market_client, market_headers, market_record, conversation, ai_gateway, payload
):
    ai_gateway.prices = ["8"]
    first = ask(market_client, market_headers, conversation, "Charge $8?")
    assert first.status_code == 200
    first_scenario = first.json()["answer"]["evidence"][-1]["data"]["scenarios"][0]
    payload["costs"][0]["amount"] = "900"
    new = market_client.post(
        market_record["path"] + "/analyses", headers=market_headers, json=payload
    )
    assert new.status_code == 201
    ai_gateway.prices = []
    ai_gateway.calls.clear()
    second = ask(market_client, market_headers, conversation, "Why that price?", revision=1)
    assert second.status_code == 200
    evidence = second.json()["answer"]["evidence"]
    assert evidence[1]["data"]["analysis_id"] == new.json()["id"]
    assert evidence[-1]["data"]["scenarios"][0] != first_scenario
    assert ai_gateway.calls[-1]["messages"][1]["role"] == "user"
    assert ai_gateway.calls[-1]["messages"][2]["role"] == "user"  # stale answer omitted
    history = turns(market_client, market_headers, conversation).json()["items"]
    assert history[0]["answer"] is None
    assert history[0]["answer_status"] == "evidence_changed"
    assert history[1]["answer_status"] == "available"


def test_buyer_continuity_never_receives_seller_dialogue(
    market_client, market_headers, public_listing, conversation, ai_gateway
):
    assert (
        ask(market_client, market_headers, conversation, "PRIVATE_CONVERSATION_MARKER").status_code
        == 200
    )
    buyer = market_client.post(
        PATH,
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {"role": "buyer", "listing_ids": [public_listing["id"]]},
        },
    )
    assert buyer.status_code == 201
    buyer = buyer.json()
    ai_gateway.calls.clear()
    assert (
        ask(
            market_client, market_headers, buyer, "Explain the missing labor disclosure."
        ).status_code
        == 200
    )
    follow_up = ask(market_client, market_headers, buyer, "Why is that important?", revision=1)
    assert follow_up.status_code == 200
    assert follow_up.json()["context_turns"] == 1
    messages = json.dumps(ai_gateway.calls)
    assert "missing labor disclosure" in messages
    assert "PRIVATE_CONVERSATION_MARKER" not in messages
    assert "PRIVATE_MARKET" not in messages
    assert follow_up.json()["answer"]["role"] == "buyer"


def test_withdrawal_blocks_buyer_history_and_follow_up_but_not_deletion(
    market_client, market_headers, market_record, public_listing, ai_gateway
):
    buyer = market_client.post(
        PATH,
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {"role": "buyer", "listing_ids": [public_listing["id"]]},
        },
    ).json()
    assert ask(market_client, market_headers, buyer).status_code == 200
    withdrawn = market_client.post(
        market_record["path"] + "/listing/deactivate", headers=market_headers
    )
    assert withdrawn.status_code == 204
    calls = len(ai_gateway.calls)
    assert turns(market_client, market_headers, buyer).status_code == 404
    assert ask(market_client, market_headers, buyer, revision=1).status_code == 404
    assert len(ai_gateway.calls) == calls
    assert market_client.delete(PATH + "/" + buyer["id"], headers=market_headers).status_code == 204


def test_owner_binding_and_immutable_scope(
    market_client, market_headers, market_account, conversation, ai_gateway
):
    outsider = market_account(email="other-conversation@example.com")
    for path in (PATH + "/" + conversation["id"], PATH + "/" + conversation["id"] + "/turns"):
        response = market_client.get(path, headers=outsider)
        assert response.status_code == 404
        assert response.headers["Cache-Control"] == "no-store"
    assert ask(market_client, outsider, conversation).status_code == 404
    # DELETE conceals existence and never deletes another owner's record.
    assert (
        market_client.delete(PATH + "/" + conversation["id"], headers=outsider).status_code == 204
    )
    assert (
        market_client.get(PATH + "/" + conversation["id"], headers=market_headers).status_code
        == 200
    )
    response = market_client.post(
        PATH + "/" + conversation["id"] + "/turns",
        headers=market_headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": 0,
            "question": "Explain.",
            "scope": {"role": "buyer"},
        },
    )
    assert response.status_code == 422
    assert ai_gateway.calls == []


def test_create_and_turn_retries_conflicts_and_pagination(
    market_client, market_headers, seller_question, ai_gateway
):
    body = {
        "request_id": str(uuid4()),
        "scope": {"role": "seller", "product_id": seller_question["product_id"]},
    }
    first = market_client.post(PATH, headers=market_headers, json=body)
    again = market_client.post(PATH, headers=market_headers, json=body)
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    changed = {**body, "scope": {**body["scope"], "analysis_id": seller_question["analysis_id"]}}
    assert market_client.post(PATH, headers=market_headers, json=changed).status_code == 409
    conversation = first.json()
    request_id = str(uuid4())
    sent = ask(market_client, market_headers, conversation, request_id=request_id)
    calls = len(ai_gateway.calls)
    retried = ask(market_client, market_headers, conversation, request_id=request_id)
    assert sent.status_code == retried.status_code == 200
    assert sent.json() == retried.json()
    assert len(ai_gateway.calls) == calls
    assert (
        ask(
            market_client, market_headers, conversation, "Changed question", request_id=request_id
        ).status_code
        == 409
    )
    assert ask(market_client, market_headers, conversation).status_code == 409
    page = market_client.get(PATH + "?limit=1&offset=0", headers=market_headers).json()
    assert len(page["items"]) == 1
    assert market_client.get(PATH + "?limit=21", headers=market_headers).status_code == 422
    assert market_client.get(PATH + "?offset=-1", headers=market_headers).status_code == 422
    assert (
        market_client.get(
            PATH + "/" + conversation["id"] + "/turns?offset=1", headers=market_headers
        ).json()["items"]
        == []
    )


@pytest.mark.parametrize("mutation", ["logout", "seller_role", "product"])
def test_access_revalidated_after_inference_and_no_partial_turn(
    market_client, market_headers, conversation, ai_gateway, mutation
):
    def revoke():
        with Session(market_client.app.state.engine) as db, db.begin():
            table = {"logout": LoginSession, "seller_role": AccountRole, "product": Product}[
                mutation
            ]
            if mutation == "product":
                db.execute(update(Product).values(account_id="no-longer-owned"))
            elif mutation == "seller_role":
                db.execute(delete(table).where(AccountRole.role == "seller"))
            else:
                db.execute(delete(table))

    # Changing ownership must still reference an actual account.
    if mutation == "product":
        from fairmade.models import Account

        with Session(market_client.app.state.engine) as db, db.begin():
            db.add(
                Account(id="no-longer-owned", email="new-owner@example.com", password_hash="unused")
            )
    ai_gateway.after_answer = revoke
    response = ask(market_client, market_headers, conversation)
    assert response.status_code == {"logout": 401, "seller_role": 403, "product": 404}[mutation]
    with Session(market_client.app.state.engine) as db:
        assert db.get(AssistantConversation, conversation["id"]).revision == 0
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


def test_deletion_during_inference_does_not_resurrect_conversation(
    market_client, market_headers, conversation, ai_gateway
):
    def remove():
        deleted = market_client.delete(PATH + "/" + conversation["id"], headers=market_headers)
        assert deleted.status_code == 204

    ai_gateway.after_answer = remove
    assert ask(market_client, market_headers, conversation).status_code == 404
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(AssistantConversation)) == 0
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


def test_compare_and_swap_conflict_does_not_append(
    market_client, market_headers, conversation, ai_gateway
):
    def concurrent_change():
        with Session(market_client.app.state.engine) as db, db.begin():
            db.execute(update(AssistantConversation).values(revision=1))

    ai_gateway.after_answer = concurrent_change
    response = ask(market_client, market_headers, conversation)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REVISION_CONFLICT"
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


@pytest.mark.parametrize("same_key", [False, True])
def test_parallel_turns_commit_one_revision(
    market_client, market_headers, conversation, ai_gateway, monkeypatch, same_key
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    both_generated = Barrier(2)
    original = conversation_service.answer

    def race(*args, **kwargs):
        response = original(*args, **kwargs)
        both_generated.wait(timeout=10)
        return response

    monkeypatch.setattr(conversation_service, "answer", race)
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(ask, market_client, market_headers, conversation, request_id=key)
        # The first inference must finish before the second acquires the shared
        # GPU slot; its final write is held at the barrier without a DB write lock.
        import time

        deadline = time.monotonic() + 5
        while both_generated.n_waiting != 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert both_generated.n_waiting == 1
        second = pool.submit(
            ask,
            market_client,
            market_headers,
            conversation,
            request_id=key if same_key else str(uuid4()),
        )
        responses = [first.result(timeout=15), second.result(timeout=15)]
    assert sorted(row.status_code for row in responses) == ([200, 200] if same_key else [200, 409])
    if same_key:
        assert responses[0].json() == responses[1].json()
    with Session(market_client.app.state.engine) as db:
        assert db.get(AssistantConversation, conversation["id"]).revision == 1
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 1


def test_evidence_changed_after_generation_rolls_back_final_revision(
    market_client, market_headers, conversation, ai_gateway, monkeypatch
):
    original = conversation_service.answer

    def changed(*args, **kwargs):
        response = original(*args, **kwargs)
        with Session(market_client.app.state.engine) as db, db.begin():
            db.execute(update(Product).values(name="Changed after inference recheck"))
        return response

    monkeypatch.setattr(conversation_service, "answer", changed)
    response = ask(market_client, market_headers, conversation)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ASSISTANT_EVIDENCE_CHANGED"
    with Session(market_client.app.state.engine) as db:
        assert db.get(AssistantConversation, conversation["id"]).revision == 0
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


def test_failed_model_is_retryable_and_no_history_is_saved(
    market_client, market_headers, conversation, ai_gateway
):
    request_id = str(uuid4())
    ai_gateway.output = {"paragraphs": [{"text": "Invented cost 99", "evidence_keys": ["e1"]}]}
    assert (
        ask(market_client, market_headers, conversation, request_id=request_id).status_code == 502
    )
    assert turns(market_client, market_headers, conversation).json()["items"] == []
    ai_gateway.output = None
    assert (
        ask(market_client, market_headers, conversation, request_id=request_id).status_code == 200
    )


def test_expiry_purge_and_deletion_cascade(market_client, market_headers, conversation, ai_gateway):
    assert ask(market_client, market_headers, conversation).status_code == 200
    before = datetime.now(UTC)
    read = market_client.get(PATH + "/" + conversation["id"], headers=market_headers).json()
    expiry = datetime.fromisoformat(read["expires_at"])
    assert timedelta(days=29) < expiry - before <= timedelta(days=30)
    # Reads do not extend retention.
    assert (
        market_client.get(PATH + "/" + conversation["id"], headers=market_headers).json()[
            "expires_at"
        ]
        == read["expires_at"]
    )
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(update(AssistantConversation).values(expires_at=before - timedelta(seconds=1)))
    assert market_client.get(PATH, headers=market_headers).json()["items"] == []
    assert turns(market_client, market_headers, conversation).status_code == 404
    assert ask(market_client, market_headers, conversation, revision=1).status_code == 404
    with Session(market_client.app.state.engine) as db, db.begin():
        assert repository.purge_expired(db) == 1
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


def test_new_login_resumes_saved_conversation(
    market_client, market_headers, conversation, ai_gateway
):
    assert ask(market_client, market_headers, conversation).status_code == 200
    assert market_client.post("/api/v1/auth/logout", headers=market_headers).status_code == 204
    assert turns(market_client, market_headers, conversation).status_code == 401
    login = market_client.post(
        "/api/v1/auth/login",
        json={
            "email": "private-market-seller@example.com",
            "password": "synthetic-market-password",
        },
    )
    assert login.status_code == 200
    new_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    follow_up = ask(market_client, new_headers, conversation, "Tell me more.", revision=1)
    assert follow_up.status_code == 200
    assert follow_up.json()["context_turns"] == 1
    assert len(turns(market_client, new_headers, conversation).json()["items"]) == 2


def test_only_completed_new_turns_extend_retention(
    market_client, market_headers, conversation, ai_gateway
):
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(
            update(AssistantConversation).values(expires_at=datetime.now(UTC) + timedelta(days=5))
        )
    prior = market_client.get(PATH + "/" + conversation["id"], headers=market_headers).json()
    key = str(uuid4())
    assert ask(market_client, market_headers, conversation, request_id=key).status_code == 200
    after = market_client.get(PATH + "/" + conversation["id"], headers=market_headers).json()
    assert datetime.fromisoformat(after["expires_at"]) > datetime.fromisoformat(prior["expires_at"])
    assert ask(market_client, market_headers, conversation, request_id=key).status_code == 200
    assert (
        market_client.get(PATH + "/" + conversation["id"], headers=market_headers).json()[
            "expires_at"
        ]
        == after["expires_at"]
    )
    ai_gateway.output = {"paragraphs": []}
    assert ask(market_client, market_headers, conversation, revision=1).status_code == 502
    assert (
        market_client.get(PATH + "/" + conversation["id"], headers=market_headers).json()[
            "expires_at"
        ]
        == after["expires_at"]
    )


def test_operator_purge_uses_configured_database_and_preserves_active(
    market_client, market_headers, conversation, capsys
):
    from fairmade.conversations.purge import main

    another = market_client.post(
        PATH,
        headers=market_headers,
        json={"request_id": str(uuid4()), "scope": conversation["scope"]},
    ).json()
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(
            update(AssistantConversation)
            .where(AssistantConversation.id == conversation["id"])
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    main()
    assert capsys.readouterr().out == "Purged 1 expired assistant conversations.\n"
    with Session(market_client.app.state.engine) as db:
        assert db.get(AssistantConversation, conversation["id"]) is None
        assert db.get(AssistantConversation, another["id"]) is not None


def test_owner_can_erase_after_role_revocation(
    market_client, market_headers, conversation, ai_gateway
):
    assert ask(market_client, market_headers, conversation).status_code == 200
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(delete(AccountRole).where(AccountRole.role == "seller"))
    assert turns(market_client, market_headers, conversation).status_code == 403
    assert (
        market_client.delete(PATH + "/" + conversation["id"], headers=market_headers).status_code
        == 204
    )
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


def test_atomic_rollback_when_turn_insert_fails(
    market_client, market_headers, conversation, ai_gateway, monkeypatch
):
    original = Session.add

    def fail(db, record, **kwargs):
        if isinstance(record, AssistantTurn):
            raise RuntimeError("synthetic insert failure")
        return original(db, record, **kwargs)

    monkeypatch.setattr(Session, "add", fail)
    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        ask(market_client, market_headers, conversation)
    with Session(market_client.app.state.engine) as db:
        assert db.get(AssistantConversation, conversation["id"]).revision == 0
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


def test_caps_and_bounded_dialogue(
    market_client, market_headers, conversation, ai_gateway, monkeypatch
):
    monkeypatch.setattr(repository, "MAX_CONVERSATIONS", 1)
    response = market_client.post(
        PATH,
        headers=market_headers,
        json={"request_id": str(uuid4()), "scope": conversation["scope"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONVERSATION_LIMIT"
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(update(AssistantConversation).values(revision=40))
    response = ask(market_client, market_headers, conversation, revision=40)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONVERSATION_FULL"
    from fairmade.assistants.dialogue import source_digest
    from fairmade.assistants.schemas import Evidence

    facts = [Evidence(key="e1", title="Synthetic", basis="application_policy", data={})]
    dialogue = Dialogue(
        turns=[PriorTurn("x" * 2000, ("y" * 1200,), source_digest(facts)) for _ in range(10)]
    )
    messages = dialogue.messages(facts)
    assert 0 < dialogue.context_turns <= 6
    assert sum(len(row["content"].encode()) for row in messages) <= 12000


def test_history_period_retained_for_follow_up(
    market_client, market_headers, conversation, ai_gateway
):
    first = ask(market_client, market_headers, conversation, "Explain sales last month.")
    assert first.status_code == 200
    original = first.json()["answer"]["evidence"][-2]["data"]
    follow_up = ask(market_client, market_headers, conversation, "Why is that missing?", revision=1)
    assert follow_up.status_code == 200
    assert follow_up.json()["answer"]["evidence"][-2]["data"] == original


def test_creation_requires_current_role_owned_sources_and_unique_buyer_scope(
    market_client, market_headers, market_account, conversation, public_listing
):
    outsider = market_account(email="other-scope@example.com")
    buyer = market_account(email="buyer-scope@example.com", roles=())
    body = {"request_id": str(uuid4()), "scope": conversation["scope"]}
    assert market_client.post(PATH, headers=outsider, json=body).status_code == 404
    assert market_client.post(PATH, headers=buyer, json=body).status_code == 403
    duplicate = {
        "request_id": str(uuid4()),
        "scope": {"role": "buyer", "listing_ids": [public_listing["id"], public_listing["id"]]},
    }
    assert market_client.post(PATH, headers=market_headers, json=duplicate).status_code == 422


def test_history_and_deletion_work_with_inference_disabled(
    market_client, market_headers, conversation, ai_gateway, monkeypatch
):
    assert ask(market_client, market_headers, conversation).status_code == 200
    del market_client.app.state.assistant_gateway
    monkeypatch.setenv("FAIRMADE_ASSISTANTS_ENABLED", "false")
    assert turns(market_client, market_headers, conversation).status_code == 200
    assert market_client.get(PATH, headers=market_headers).status_code == 200
    assert ask(market_client, market_headers, conversation, revision=1).status_code == 503
    assert (
        market_client.delete(PATH + "/" + conversation["id"], headers=market_headers).status_code
        == 204
    )


def test_validation_no_auth_or_raw_body_echo(
    market_client, market_headers, conversation, ai_gateway
):
    assert market_client.get(PATH).status_code == 401
    assert market_client.delete(PATH + "/" + conversation["id"]).status_code == 401
    response = market_client.post(
        PATH + "/" + conversation["id"] + "/turns",
        headers=market_headers,
        json={
            "request_id": "SECRET_INVALID_ID",
            "question": "PRIVATE_VALIDATION_BODY",
            "expected_revision": True,
        },
    )
    assert response.status_code == 422
    assert "SECRET_INVALID_ID" not in response.text
    assert "PRIVATE_VALIDATION_BODY" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
