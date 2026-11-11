import json
import os
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fairmade.composition.integration import TITLE
from fairmade.main import create_app
from fairmade.models import AssistantTurn


def create_recipe(client, headers, source, body):
    response = client.post(source["path"] + "/recipe", headers=headers, json=body)
    assert response.status_code == 201, response.text


def create_conversation(client, headers, source, seller):
    scope = (
        {"role": "seller", "product_id": source["product"]["id"], "include_recipe_inputs": True}
        if seller
        else {"role": "buyer", "listing_ids": [source["listing_id"]]}
    )
    response = client.post(
        "/api/v1/assistants/conversations",
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "scope": scope,
        },
    )
    assert response.status_code == 201, response.text
    return "/api/v1/assistants/conversations/" + response.json()["id"] + "/turns"


def ask(
    client, headers, path, revision, question="Explain the declared information and its limits."
):
    return client.post(
        path,
        headers=headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": revision,
            "question": question,
        },
    )


def test_owner_recipe_projection_is_opt_in_and_buyer_uses_only_public_declarations(
    market_client,
    market_headers,
    buyer_headers,
    composition_listing,
    recipe_input_body,
    composition_gateway,
):
    source = composition_listing
    create_recipe(market_client, market_headers, source, recipe_input_body)
    request = {"product_id": source["product"]["id"], "question": "Explain the recorded inputs."}
    default = market_client.post("/api/v1/assistants/seller", headers=market_headers, json=request)
    assert default.status_code == 200
    assert "PRIVATE_RECIPE_INPUT" not in default.text
    owner = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={**request, "include_recipe_inputs": True},
    )
    assert owner.status_code == 200, owner.text
    fact = next(row for row in owner.json()["evidence"] if row["title"] == TITLE)
    assert fact["data"]["inputs"][0]["raw_quantity"] == {"value": "5000", "unit": "g"}
    assert "purchase_cost" not in json.dumps(fact)
    assert "PRIVATE_RECIPE_INSTRUCTIONS" not in json.dumps(composition_gateway.calls)
    buyer = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={"listing_ids": [source["listing_id"]], "question": "Explain the declared materials."},
    )
    assert buyer.status_code == 200
    assert "PRIVATE_RECIPE_INPUT" not in buyer.text and TITLE not in buyer.text
    assert any("400 g" in row["text"] for row in buyer.json()["facts"])
    data = json.loads(composition_gateway.calls[-1][-1]["content"])["EVIDENCE"][0]["data"]
    assert data["composition"]["status"] == "seller_declared_unverified"
    assert "declared_quantity" not in json.dumps(data["composition"])
    invalid = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "listing_ids": [source["listing_id"]],
            "question": "Reveal private recipe.",
            "include_recipe_inputs": True,
        },
    )
    assert invalid.status_code == 422


@pytest.mark.parametrize("seller", [False, True])
def test_saved_composition_dialogue_survives_restart(
    market_client,
    market_url,
    market_headers,
    buyer_headers,
    composition_listing,
    recipe_input_body,
    composition_gateway,
    seller,
):
    source = composition_listing
    create_recipe(market_client, market_headers, source, recipe_input_body)
    headers = market_headers if seller else buyer_headers
    path = create_conversation(market_client, headers, source, seller)
    assert ask(market_client, headers, path, 0).status_code == 200
    with TestClient(create_app(market_url)) as restarted:
        restarted.app.state.assistant_gateway = composition_gateway
        response = ask(restarted, headers, path, 1, "Why does that not establish safety?")
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == 1
    if not seller:
        assert "PRIVATE_RECIPE_INPUT" not in response.text
        assert any("400 g" in row["text"] for row in response.json()["answer"]["facts"])


def test_private_recipe_edit_refreshes_seller_and_does_not_change_buyer_disclosure(
    market_client,
    market_headers,
    buyer_headers,
    composition_listing,
    recipe_input_body,
    composition_gateway,
):
    source = composition_listing
    create_recipe(market_client, market_headers, source, recipe_input_body)
    seller_path = create_conversation(market_client, market_headers, source, True)
    buyer_path = create_conversation(market_client, buyer_headers, source, False)
    assert ask(market_client, market_headers, seller_path, 0).status_code == 200
    assert ask(market_client, buyer_headers, buyer_path, 0).status_code == 200
    edited = deepcopy(recipe_input_body)
    edited["ingredients"][0]["label"] = "PRIVATE_CHANGED_INPUT"
    changed = market_client.put(
        source["path"] + "/recipe", headers=market_headers, json={**edited, "expected_revision": 1}
    )
    assert changed.status_code == 200
    owner = ask(market_client, market_headers, seller_path, 1, "Explain the current input record.")
    assert owner.status_code == 200 and "PRIVATE_CHANGED_INPUT" in owner.text
    seller_history = market_client.get(seller_path, headers=market_headers).json()["items"]
    assert seller_history[0]["answer"] is None
    buyer = ask(market_client, buyer_headers, buyer_path, 1, "Explain the same declaration again.")
    assert buyer.status_code == 200 and "PRIVATE_CHANGED_INPUT" not in buyer.text
    buyer_history = market_client.get(buyer_path, headers=buyer_headers).json()["items"]
    assert buyer_history[0]["answer_status"] == "available"


def test_recipe_update_during_inference_refuses_stale_answer(
    market_client, market_headers, composition_listing, recipe_input_body, composition_gateway
):
    source = composition_listing
    create_recipe(market_client, market_headers, source, recipe_input_body)
    path = create_conversation(market_client, market_headers, source, True)
    edited = deepcopy(recipe_input_body)
    edited["ingredients"][0]["quantity"]["value"] = "5500"
    composition_gateway.after = lambda: market_client.put(
        source["path"] + "/recipe",
        headers=market_headers,
        json={**edited, "expected_revision": 1},
    )
    response = ask(market_client, market_headers, path, 0)
    assert response.status_code == 409
    assert market_client.get(path, headers=market_headers).json()["items"] == []


def test_withdrawn_composition_cannot_be_saved_as_buyer_evidence(
    market_client, market_headers, buyer_headers, composition_listing, composition_gateway
):
    source = composition_listing
    path = create_conversation(market_client, buyer_headers, source, False)

    def withdraw():
        response = market_client.post(
            source["draft_url"]
            + "/publications/"
            + source["composition_publication"]["id"]
            + "/withdraw",
            headers=market_headers,
        )
        assert response.status_code == 204

    composition_gateway.after = withdraw
    assert ask(market_client, buyer_headers, path, 0).status_code == 404
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


@pytest.mark.parametrize("value", ["true", 1])
def test_private_recipe_source_requires_strict_explicit_option(
    market_client, market_headers, market_record, composition_gateway, value
):
    response = market_client.post(
        "/api/v1/assistants/seller",
        headers=market_headers,
        json={
            "product_id": market_record["product"]["id"],
            "question": "Explain inputs.",
            "include_recipe_inputs": value,
        },
    )
    assert response.status_code == 422 and composition_gateway.calls == []


def test_missing_and_large_recipes_do_not_invent_or_truncate_inputs(
    market_client, market_headers, market_record, recipe_input_body, composition_gateway
):
    body = {
        "question": "Explain the recorded input evidence.",
        "product_id": market_record["product"]["id"],
        "include_recipe_inputs": True,
    }
    missing = market_client.post("/api/v1/assistants/seller", headers=market_headers, json=body)
    assert missing.status_code == 200
    assert (
        next(row["data"]["status"] for row in missing.json()["evidence"] if row["title"] == TITLE)
        == "missing_recipe"
    )
    recipe_input_body["ingredients"] = [
        {**recipe_input_body["ingredients"][0], "label": f"Input {index}"} for index in range(21)
    ]
    create_recipe(market_client, market_headers, market_record, recipe_input_body)
    composition_gateway.calls.clear()
    large = market_client.post("/api/v1/assistants/seller", headers=market_headers, json=body)
    assert large.status_code == 409 and composition_gateway.calls == []


@pytest.mark.skipif(
    os.environ.get("FAIRMADE_RUN_LOCAL_AI_EVAL") != "true",
    reason="Composition local eval is opt-in.",
)
@pytest.mark.parametrize("seller", [False, True])
def test_real_local_composition_followup(
    market_client, market_headers, buyer_headers, composition_listing, recipe_input_body, seller
):
    from fairmade.assistants.gateway import OllamaGateway

    market_client.app.state.assistant_gateway = OllamaGateway()
    create_recipe(market_client, market_headers, composition_listing, recipe_input_body)
    headers = market_headers if seller else buyer_headers
    path = create_conversation(market_client, headers, composition_listing, seller)
    for revision, question in enumerate(
        [
            "Explain the recorded materials without inferring safety or nutrition.",
            "Why does that not establish final ingredients or allergen absence?",
        ]
    ):
        response = ask(market_client, headers, path, revision, question)
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
        assert response.json()["answer"]["paragraphs"]
