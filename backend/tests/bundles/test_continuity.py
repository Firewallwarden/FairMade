import json
import os
from uuid import uuid4

import pytest
from baskets.conftest import PROFILE, save_profile
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.bundles.integration import TITLE
from fairmade.main import create_app
from fairmade.models import AssistantTurn, PassportPublication, SellableInventory


def create(client, headers, body, *, product_id=None):
    scope = {"role": "seller" if product_id else "buyer", "bundles": body}
    if product_id:
        scope["product_id"] = product_id
    response = client.post(
        "/api/v1/assistants/conversations",
        headers=headers,
        json={"request_id": str(uuid4()), "scope": scope},
    )
    assert response.status_code == 201, response.text
    return "/api/v1/assistants/conversations/" + response.json()["id"] + "/turns"


def ask(client, headers, path, revision, question="Explain the suggested pair."):
    return client.post(
        path,
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": revision,
            "question": question,
        },
    )


@pytest.mark.parametrize("seller", [False, True])
def test_saved_pair_followups_survive_restart(
    market_client,
    market_url,
    market_headers,
    buyer_headers,
    bundle_body,
    bundle_sources,
    bundle_gateway,
    seller,
):
    headers = market_headers if seller else buyer_headers
    product_id = bundle_sources[0]["product"]["id"] if seller else None
    path = create(market_client, headers, bundle_body, product_id=product_id)
    first = ask(market_client, headers, path, 0)
    assert first.status_code == 200, first.text
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = bundle_gateway
        second = ask(restarted, headers, path, 1, "Why does that not establish a saving?")
        assert second.status_code == 200, second.text
        assert second.json()["context_turns"] == 1
        report = next(
            row["data"]["report"]
            for row in second.json()["answer"]["evidence"]
            if row["title"] == TITLE
        )
        assert report["suggestions"][0]["subtotal"]["amount"] == "0.30"
    model_facts = json.loads(bundle_gateway.calls[-1][-1]["content"])["EVIDENCE"]
    context = json.dumps(next(fact["data"] for fact in model_facts if fact["title"] == TITLE))
    assert '"amount"' not in context and "PRIVATE_MARKET" not in context
    assert "observed_copurchase_orders" not in context


def test_profile_erasure_removes_bundle_answer_copies(
    market_client, buyer_headers, bundle_body, bundle_gateway
):
    save_profile(market_client, buyer_headers, {})
    path = create(market_client, buyer_headers, bundle_body)
    assert ask(market_client, buyer_headers, path, 0).status_code == 200
    erased = market_client.request(
        "DELETE", PROFILE, headers=buyer_headers, json={"expected_revision": 1}
    )
    assert erased.status_code == 200
    history = market_client.get(path, headers=buyer_headers)
    assert history.status_code == 200
    assert history.json()["items"][0]["answer"] is None
    with Session(market_client.app.state.engine) as db:
        rows = db.scalars(select(AssistantTurn)).all()
        assert len(rows) == 1 and rows[0].response["evidence"] == []


def test_followup_recomputes_stock_and_withholds_previous_recommendation(
    market_client, buyer_headers, bundle_body, bundle_sources, bundle_gateway
):
    path = create(market_client, buyer_headers, bundle_body)
    assert ask(market_client, buyer_headers, path, 0).status_code == 200
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(
            update(SellableInventory)
            .where(SellableInventory.product_id == bundle_sources[0]["product"]["id"])
            .values(on_hand=0)
        )
    response = ask(market_client, buyer_headers, path, 1, "Which pair is available now?")
    assert response.status_code == 200
    data = next(
        row["data"]["report"]
        for row in response.json()["answer"]["evidence"]
        if row["title"] == TITLE
    )
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["subtotal"]["amount"] == "5.21"
    history = market_client.get(path, headers=buyer_headers).json()["items"]
    assert history[0]["answer"] is None and history[0]["answer_status"] == "evidence_changed"


@pytest.mark.parametrize("change,expected", [("stock", 409), ("logout", 401), ("withdraw", 404)])
def test_source_changes_during_inference_refuse_stale_bundle(
    market_client, market_headers, buyer_headers, bundle_body, bundle_gateway, change, expected
):
    path = create(market_client, buyer_headers, bundle_body)

    def mutate():
        if change == "stock":
            with Session(market_client.app.state.engine) as db, db.begin():
                db.execute(update(SellableInventory).values(on_hand=0))
        elif change == "logout":
            market_client.post("/api/v1/auth/logout", headers=buyer_headers)
        else:
            market_client.post(
                "/api/v1/seller/storefronts/" + bundle_body["storefront_id"] + "/withdraw",
                headers=market_headers,
            )

    bundle_gateway.after = mutate
    response = ask(market_client, buyer_headers, path, 0)
    assert response.status_code == expected, response.text


def test_quality_concern_cannot_be_overridden_by_favorites(
    market_client, buyer_headers, bundle_sources, bundle_body
):
    save_profile(market_client, buyer_headers, {})
    listing = bundle_sources[0]
    market_client.post(
        "/api/v1/favorites", headers=buyer_headers, json={"listing_id": listing["listing"]["id"]}
    )
    with Session(market_client.app.state.engine) as db, db.begin():
        publication = db.get(PassportPublication, listing["publication"]["id"])
        publication.payload = {
            **publication.payload,
            "quality_summary": {
                "status": "needs_attention",
                "evaluation_count": 1,
                "failed_count": 1,
                "unknown_or_unevaluated_count": 0,
                "outdated_count": 0,
            },
        }
    response = market_client.post(
        "/api/v1/buyer/bundles/suggest", headers=buyer_headers, json=bundle_body
    )
    assert response.status_code == 200
    assert "QUALITY_REQUIRES_ATTENTION" in response.json()["candidates"][0]["exclusions"]
    assert len(response.json()["suggestions"]) == 1
    assert response.json()["suggestions"][0]["subtotal"]["amount"] == "5.21"


def test_pair_budget_cannot_be_remembered_as_per_item_budget(
    market_client, buyer_headers, bundle_body, bundle_gateway
):
    save_profile(market_client, buyer_headers, {})
    path = create(market_client, buyer_headers, bundle_body)
    turn = ask(market_client, buyer_headers, path, 0, "My bundle budget is $10 total.")
    assert turn.status_code == 200
    response = market_client.post(
        PROFILE + "/remember",
        headers=buyer_headers,
        json={
            "conversation_id": path.split("/")[-2],
            "turn_id": turn.json()["id"],
        },
    )
    assert response.status_code == 502
    assert (
        market_client.get(PROFILE, headers=buyer_headers).json()["preferences"]["budget_per_item"]
        is None
    )


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Local bundle evaluation is opt-in.",
)
@pytest.mark.parametrize("seller", [False, True])
def test_real_local_pair_dialogue(
    market_client, buyer_headers, market_headers, bundle_body, bundle_sources, seller
):
    from fairmade.assistants.gateway import OllamaGateway

    market_client.app.state.assistant_gateway = OllamaGateway()
    headers = market_headers if seller else buyer_headers
    path = create(
        market_client,
        headers,
        bundle_body,
        product_id=bundle_sources[0]["product"]["id"] if seller else None,
    )
    for revision, question in enumerate(
        ["Explain the pair without assuming a discount.", "Why is that not a guaranteed saving?"]
    ):
        response = ask(market_client, headers, path, revision, question)
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
        assert any("USD 0.30" in row["text"] for row in response.json()["answer"]["facts"])
