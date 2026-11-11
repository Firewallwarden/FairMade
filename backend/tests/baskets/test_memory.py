import json
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.models import AssistantTurn, PassportPublication, SellableInventory

from .conftest import PATH, PROFILE, need, save_profile


def test_no_activity_without_opt_in(market_client, buyer_headers, basket_body, monkeypatch):
    import fairmade.baskets.service as service

    def forbidden(*args):
        raise AssertionError("Activity queried without consent")

    monkeypatch.setattr(service, "signals", forbidden)
    response = market_client.post(PATH, headers=buyer_headers, json=basket_body)
    assert response.status_code == 200, response.text
    assert response.json()["personalized"] is False


def test_remembered_budget_is_per_item_and_cannot_be_waived_by_total_budget(
    market_client,
    buyer_headers,
    basket_body,
):
    save_profile(market_client, buyer_headers, {"budget_per_item": "11.99"})
    basket_body["budget"] = "999.00"
    response = market_client.post(PATH, headers=buyer_headers, json=basket_body)
    assert response.status_code == 200
    result = response.json()
    assert result["personalized"] is True
    assert result["status"] == "unavailable"
    assert "ABOVE_BUDGET" in result["needs"][0]["candidates"][1]["exclusions"]
    assert result["needs"][0]["candidates"][1]["affinity_reasons"] == []
    save_profile(market_client, buyer_headers, {"budget_per_item": "12.00"})
    basket_body.pop("budget")
    result = market_client.post(PATH, headers=buyer_headers, json=basket_body).json()
    assert result["status"] == "ready"
    assert result["minimum_subtotal"]["amount"] == "31.00"  # No inferred basket limit of USD 12.
    assert result["budget"] is None


@pytest.mark.parametrize(
    "preferences,code",
    [
        ({"product_types": ["eggs"]}, "PRODUCT_TYPE_NOT_SELECTED"),
        ({"location": "Another area"}, "LOCATION_NOT_SELECTED"),
    ],
)
def test_confirmed_filters_are_hard_constraints(
    market_client,
    buyer_headers,
    basket_body,
    preferences,
    code,
):
    save_profile(market_client, buyer_headers, preferences)
    result = market_client.post(PATH, headers=buyer_headers, json=basket_body).json()
    assert result["status"] == "unavailable"
    assert code in result["needs"][0]["candidates"][0]["exclusions"]


def test_favorite_tie_break_never_overrides_cost_or_exclusion(
    market_client,
    buyer_headers,
    basket_store,
    basket_listing,
):
    first, favorite = basket_listing("12.00"), basket_listing("12.00")
    favorite_id = favorite["listing"]["id"]
    assert (
        market_client.post(
            "/api/v1/favorites", headers=buyer_headers, json={"listing_id": favorite_id}
        ).status_code
        == 201
    )
    save_profile(market_client, buyer_headers, {})
    body = {"storefront_id": basket_store, "needs": [need("bread", first, favorite)]}
    result = market_client.post(PATH, headers=buyer_headers, json=body).json()
    assert result["needs"][0]["chosen_listing_id"] == favorite_id
    cheap = basket_listing("11.99")
    body["needs"] = [need("bread", favorite, cheap)]
    result = market_client.post(PATH, headers=buyer_headers, json=body).json()
    assert result["needs"][0]["chosen_listing_id"] == cheap["listing"]["id"]
    save_profile(market_client, buyer_headers, {"excluded_listing_ids": [favorite_id]})
    body["needs"] = [need("bread", first, favorite)]
    result = market_client.post(PATH, headers=buyer_headers, json=body).json()
    assert result["needs"][0]["chosen_listing_id"] == first["listing"]["id"]


def test_disclosed_quality_attention_excludes_cheapest_favorite(
    market_client,
    buyer_headers,
    basket_store,
    basket_listing,
):
    cheap, other = basket_listing("1.00"), basket_listing("2.00")
    save_profile(market_client, buyer_headers, {})
    market_client.post(
        "/api/v1/favorites", headers=buyer_headers, json={"listing_id": cheap["listing"]["id"]}
    )
    with Session(market_client.app.state.engine) as db, db.begin():
        publication = db.get(PassportPublication, cheap["publication"]["id"])
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
        PATH,
        headers=buyer_headers,
        json={
            "storefront_id": basket_store,
            "needs": [need("bread", cheap, other)],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["needs"][0]["chosen_listing_id"] == other["listing"]["id"]
    assert (
        "QUALITY_REQUIRES_ATTENTION" in response.json()["needs"][0]["candidates"][0]["exclusions"]
    )


def test_basket_saved_dialogue_rechecks_stock_and_profile_erasure(
    market_client,
    buyer_headers,
    market_account,
    basket_body,
    basket_gateway,
):
    save_profile(market_client, buyer_headers, {"budget_per_item": "20"})
    created = market_client.post(
        "/api/v1/assistants/conversations",
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {"role": "buyer", "basket": basket_body},
        },
    )
    assert created.status_code == 201, created.text
    conversation = created.json()["id"]
    path = "/api/v1/assistants/conversations/" + conversation
    for revision, question in enumerate(
        ["Explain this basket.", "Why did you choose those alternatives?"]
    ):
        response = market_client.post(
            path + "/turns",
            headers=buyer_headers,
            json={
                "request_id": str(uuid4()),
                "expected_revision": revision,
                "question": question,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["context_turns"] == revision
    assert any("USD 31.00" in fact["text"] for fact in response.json()["answer"]["facts"])
    assert any(message["role"] == "assistant" for message in basket_gateway.calls[-1][1:-1])
    other = market_account("other-basket-buyer@example.com", roles=())
    assert market_client.get(path, headers=other).status_code == 404
    erased = market_client.request(
        "DELETE", PROFILE, headers=buyer_headers, json={"expected_revision": 1}
    )
    assert erased.status_code == 200
    turns = market_client.get(path + "/turns", headers=buyer_headers)
    assert turns.status_code == 200, turns.text
    assert all(turn["answer"] is None for turn in turns.json()["items"])
    with Session(market_client.app.state.engine) as db:
        for row in db.scalars(
            select(AssistantTurn).where(AssistantTurn.conversation_id == conversation)
        ):
            assert row.response["evidence"] == [] and row.response["paragraphs"] == []
    current = market_client.post(
        path + "/turns",
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": 2,
            "question": "Explain the current basket again.",
        },
    )
    assert current.status_code == 200, current.text
    with Session(market_client.app.state.engine) as db, db.begin():
        db.execute(update(SellableInventory).values(on_hand=0))
    turns = market_client.get(path + "/turns", headers=buyer_headers)
    assert turns.status_code == 200
    assert all(turn["answer"] is None for turn in turns.json()["items"])


@pytest.mark.parametrize("change", ["stock", "profile", "logout", "withdraw"])
def test_changes_during_inference_do_not_return_stale_plan(
    market_client,
    buyer_headers,
    market_headers,
    basket_body,
    basket_gateway,
    change,
):
    save_profile(market_client, buyer_headers, {})

    def mutate():
        if change == "stock":
            with Session(market_client.app.state.engine) as db, db.begin():
                db.execute(update(SellableInventory).values(on_hand=0))
        elif change == "profile":
            market_client.request(
                "DELETE", PROFILE, headers=buyer_headers, json={"expected_revision": 1}
            )
        elif change == "logout":
            market_client.post("/api/v1/auth/logout", headers=buyer_headers)
        else:
            market_client.post(
                "/api/v1/seller/storefronts/" + basket_body["storefront_id"] + "/withdraw",
                headers=market_headers,
            )

    basket_gateway.after = mutate
    response = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "question": "Explain this basket.",
            "basket": basket_body,
        },
    )
    assert (
        response.status_code
        == {"stock": 409, "profile": 409, "logout": 401, "withdraw": 404}[change]
    ), response.text


def test_basket_model_context_does_not_expose_raw_activity_or_exact_prices(
    market_client,
    buyer_headers,
    basket_body,
    basket_gateway,
):
    save_profile(market_client, buyer_headers, {"budget_per_item": "20", "location": "Exampletown"})
    response = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={
            "question": "Explain this basket.",
            "basket": basket_body,
        },
    )
    assert response.status_code == 200, response.text
    context = json.loads(basket_gateway.calls[-1][-1]["content"])["EVIDENCE"]
    text = json.dumps(context)
    assert '"amount"' not in text
    assert '"favorites"' not in text and '"purchases"' not in text
    assert '"location": "Exampletown"' not in text
    assert "PRIVATE_MARKET" not in text


def test_basket_or_listing_scope_is_required(
    market_client, buyer_headers, basket_body, basket_gateway
):
    for extra in [
        {},
        {"listing_ids": [], "basket": None},
        {"listing_ids": [str(uuid4())], "basket": basket_body},
    ]:
        response = market_client.post(
            "/api/v1/assistants/buyer",
            headers=buyer_headers,
            json={"question": "Explain.", **extra},
        )
        assert response.status_code == 422


@pytest.mark.parametrize(
    "question,expected",
    [
        ("My basket budget is $40 total.", 502),
        ("My per-item budget is $40.", 200),
    ],
)
def test_basket_budget_cannot_be_proposed_as_per_item_memory(
    market_client,
    buyer_headers,
    basket_body,
    basket_gateway,
    question,
    expected,
):
    save_profile(market_client, buyer_headers, {})
    created = market_client.post(
        "/api/v1/assistants/conversations",
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "scope": {"role": "buyer", "basket": basket_body},
        },
    )
    assert created.status_code == 201
    conversation = created.json()["id"]
    turn = market_client.post(
        "/api/v1/assistants/conversations/" + conversation + "/turns",
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "expected_revision": 0,
            "question": question,
        },
    )
    assert turn.status_code == 200, turn.text
    proposal = market_client.post(
        PROFILE + "/remember",
        headers=buyer_headers,
        json={
            "conversation_id": conversation,
            "turn_id": turn.json()["id"],
        },
    )
    assert proposal.status_code == expected, proposal.text
    assert (
        market_client.get(PROFILE, headers=buyer_headers).json()["preferences"]["budget_per_item"]
        is None
    )
