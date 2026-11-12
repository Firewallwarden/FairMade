from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from fairmade.models import PayPalCheckout

PATH = "/api/v1/buyer/personalization"


def suggest(client, headers, **body):
    return client.post(PATH + "/suggestions", headers=headers, json=body)


def test_no_activity_used_before_opt_in(market_client, buyer_headers, order_source, monkeypatch):
    import fairmade.personalization.service as service

    def forbidden(*args):
        raise AssertionError("activity queried without consent")

    monkeypatch.setattr(service, "signals", forbidden)
    response = suggest(market_client, buyer_headers)
    assert response.status_code == 200
    assert response.json()["personalized"] is False
    assert len(response.json()["items"]) == 1
    assert "PRIVATE_MARKET" not in response.text


def test_favorites_never_override_budget_or_exclusion(
    market_client, buyer_headers, order_source, enabled_profile
):
    listing_id = order_source["listing"]["id"]
    assert (
        market_client.post(
            "/api/v1/favorites", headers=buyer_headers, json={"listing_id": listing_id}
        ).status_code
        == 201
    )
    saved = market_client.put(
        PATH,
        headers=buyer_headers,
        json={
            "expected_revision": 1,
            "enabled": True,
            "confirmed": True,
            "preferences": {"budget_per_item": "16.999999"},
        },
    )
    assert saved.status_code == 200
    assert suggest(market_client, buyer_headers).json()["items"] == []
    override = suggest(market_client, buyer_headers, budget_per_item="17.00")
    assert override.status_code == 200
    assert override.json()["items"][0]["reasons"] == ["IN_YOUR_FAVORITES"]
    assert (
        market_client.get(PATH, headers=buyer_headers).json()["preferences"]["budget_per_item"]
        == "16.999999"
    )
    current = market_client.get(PATH, headers=buyer_headers).json()
    market_client.put(
        PATH,
        headers=buyer_headers,
        json={
            "expected_revision": current["revision"],
            "enabled": True,
            "confirmed": True,
            "preferences": {"excluded_listing_ids": [listing_id]},
        },
    )
    assert suggest(market_client, buyer_headers, budget_per_item="999").json()["items"] == []


def test_verified_purchase_signal_requires_capture_and_is_buyer_scoped(
    paypal_client,
    buyer_headers,
    checkout,
    checkout_path,
    fake_gateway,
    enabled_profile,
    market_account,
):
    first = suggest(paypal_client, buyer_headers)
    assert "PREVIOUS_VERIFIED_SANDBOX_PURCHASE" not in first.text
    fake_gateway.approve(checkout["provider_order_id"])
    assert (
        paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={}).status_code
        == 200
    )
    paid = suggest(paypal_client, buyer_headers)
    assert paid.status_code == 200
    assert "PREVIOUS_VERIFIED_SANDBOX_PURCHASE" in paid.text
    assert "capture_id" not in paid.text and "PRIVATE_PAYER" not in paid.text
    outsider = market_account(email="new-profile-buyer@example.com", roles=())
    paypal_client.put(
        PATH,
        headers=outsider,
        json={
            "expected_revision": 0,
            "enabled": True,
            "confirmed": True,
        },
    )
    assert "PREVIOUS_VERIFIED_SANDBOX_PURCHASE" not in suggest(paypal_client, outsider).text
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.execute(
            update(PayPalCheckout).values(verified_at=datetime.now(UTC) - timedelta(days=91))
        )
    assert "PREVIOUS_VERIFIED_SANDBOX_PURCHASE" not in suggest(paypal_client, buyer_headers).text
    with Session(paypal_client.app.state.engine) as db, db.begin():
        db.execute(update(PayPalCheckout).values(verified_at=datetime.now(UTC) + timedelta(days=1)))
    assert "PREVIOUS_VERIFIED_SANDBOX_PURCHASE" not in suggest(paypal_client, buyer_headers).text


def test_withdrawal_unknown_stock_and_self_purchase_are_filtered(
    market_client, market_headers, buyer_headers, market_record, order_source, enabled_profile
):
    assert suggest(market_client, market_headers).json()["items"] == []
    assert (
        market_client.post(
            market_record["path"] + "/listing/deactivate", headers=market_headers
        ).status_code
        == 204
    )
    assert suggest(market_client, buyer_headers).json()["items"] == []


def test_deleted_profile_invalidates_old_personalized_answers(
    market_client, buyer_headers, saved_buyer_turn, profile_gateway
):
    erased = market_client.request(
        "DELETE", PATH, headers=buyer_headers, json={"expected_revision": 1}
    )
    assert erased.status_code == 200
    history = market_client.get(
        "/api/v1/assistants/conversations/" + saved_buyer_turn["conversation_id"] + "/turns",
        headers=buyer_headers,
    )
    assert history.status_code == 200
    assert history.json()["items"][0]["answer"] is None


def test_profile_change_during_buyer_answer_invalidates_result(
    market_client, buyer_headers, order_source, enabled_profile, profile_gateway
):
    def erase():
        market_client.request("DELETE", PATH, headers=buyer_headers, json={"expected_revision": 1})

    profile_gateway.after = erase
    response = market_client.post(
        "/api/v1/assistants/buyer",
        headers=buyer_headers,
        json={"listing_ids": [order_source["listing"]["id"]], "question": "Explain my options."},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ASSISTANT_EVIDENCE_CHANGED"
