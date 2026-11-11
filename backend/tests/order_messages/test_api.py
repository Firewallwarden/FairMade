import json
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fairmade.auth import hash_token
from fairmade.database import utcnow
from fairmade.main import create_app
from fairmade.models import AccountRole, LoginSession, Order, SellableInventory

from .conftest import send


def test_two_participants_restart_and_no_business_effects(
    market_client,
    market_url,
    buyer_headers,
    market_headers,
    message_path,
    message_order,
):
    order_path = "/api/v1/orders/" + message_order["id"]
    before = market_client.get(order_path, headers=buyer_headers).json()
    with Session(market_client.app.state.engine) as db:
        stock = db.scalar(select(SellableInventory.on_hand))
    assert market_client.get(message_path, headers=buyer_headers).json()["items"] == []
    first = send(market_client, buyer_headers, message_path, "When can I collect this order?")
    assert first.status_code == 201, first.text
    assert first.json()["sender"] == "buyer" and first.json()["is_mine"] is True
    assert first.json()["sequence"] == 1
    with TestClient(create_app(market_url)) as restarted:
        second = send(
            restarted, market_headers, message_path, "I will update the pickup instructions."
        )
        assert second.status_code == 201 and second.json()["sequence"] == 2
        history = restarted.get(message_path, headers=buyer_headers)
        assert history.status_code == 200
        assert history.json()["my_role"] == "buyer"
        assert [m["sender"] for m in history.json()["items"]] == ["buyer", "seller"]
        assert [m["is_mine"] for m in history.json()["items"]] == [True, False]
        assert history.json()["next_after_sequence"] == 2
        assert history.json()["has_more"] is False
        for private in ["@", "sender_account_id", "request_id", "password"]:
            assert private not in history.text
        assert history.headers["cache-control"] == "no-store"
    assert market_client.get(order_path, headers=buyer_headers).json() == before
    with Session(market_client.app.state.engine) as db:
        assert db.scalar(select(SellableInventory.on_hand)) == stock


def test_retry_normalization_and_conflict(
    market_client, buyer_headers, market_headers, message_path
):
    key = str(uuid4())
    first = send(market_client, buyer_headers, message_path, "  A question.  ", key)
    retry = send(market_client, buyer_headers, message_path, "A question.", key)
    assert first.status_code == 201 and retry.status_code == 200
    assert first.json() == retry.json()
    conflict = send(market_client, buyer_headers, message_path, "Different message.", key)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "REQUEST_ID_CONFLICT"
    other = send(market_client, market_headers, message_path, "A reply.", key)
    assert other.status_code == 201 and other.json()["sequence"] == 2


def test_cursor_history_stays_stable_during_appends(
    market_client, buyer_headers, market_headers, message_path
):
    for index in range(3):
        assert (
            send(market_client, buyer_headers, message_path, f"Question {index}").status_code == 201
        )
    first = market_client.get(message_path + "?limit=2", headers=market_headers).json()
    assert first["has_more"] and first["next_after_sequence"] == 2
    assert send(market_client, market_headers, message_path, "Another reply.").status_code == 201
    second = market_client.get(
        message_path + "?after_sequence=2&limit=2", headers=market_headers
    ).json()
    assert [m["sequence"] for m in second["items"]] == [3, 4]
    assert second["has_more"] is False
    empty = market_client.get(message_path + "?after_sequence=4", headers=buyer_headers).json()
    assert empty["items"] == [] and empty["next_after_sequence"] == 4


def test_participants_only_including_admin_outsider(
    market_client,
    buyer_headers,
    market_account,
    message_path,
):
    assert (
        send(market_client, buyer_headers, message_path, "PRIVATE_ORDER_MESSAGE").status_code == 201
    )
    for roles, email in [
        ((), "outsider-msg@example.com"),
        (("seller",), "seller-msg@example.com"),
        (("admin",), "admin-msg@example.com"),
    ]:
        outsider = market_account(email, roles=roles)
        read = market_client.get(message_path, headers=outsider)
        write = send(market_client, outsider, message_path)
        assert read.status_code == write.status_code == 404
        assert "PRIVATE_ORDER_MESSAGE" not in read.text
        assert read.headers["cache-control"] == write.headers["cache-control"] == "no-store"
    missing = "/api/v1/orders/" + str(uuid4()) + "/messages"
    assert market_client.get(missing, headers=buyer_headers).status_code == 404
    assert send(market_client, buyer_headers, missing).status_code == 404
    assert market_client.get(message_path).status_code == 401
    assert (
        market_client.post(
            message_path, json={"request_id": str(uuid4()), "text": "Question"}
        ).status_code
        == 401
    )


def test_seller_revocation_and_seller_account_buying_capabilities(
    market_client,
    buyer_headers,
    market_headers,
    message_path,
    message_order,
):
    with Session(market_client.app.state.engine) as db, db.begin():
        order = db.get(Order, message_order["id"])
        db.add(AccountRole(account_id=order.buyer_account_id, role="seller"))
        db.execute(
            delete(AccountRole).where(
                AccountRole.account_id == order.seller_account_id, AccountRole.role == "seller"
            )
        )
    assert send(market_client, buyer_headers, message_path).json()["sender"] == "buyer"
    assert market_client.get(message_path, headers=market_headers).status_code == 403
    assert send(market_client, market_headers, message_path).status_code == 403


def test_cancelled_order_keeps_messages(
    market_client, buyer_headers, market_headers, message_path, message_order
):
    assert (
        market_client.post(
            "/api/v1/orders/" + message_order["id"] + "/cancel", headers=buyer_headers
        ).status_code
        == 200
    )
    assert (
        send(market_client, buyer_headers, message_path, "Question about cancellation.").status_code
        == 201
    )
    assert (
        send(market_client, market_headers, message_path, "Cancellation reply.").status_code == 201
    )


def test_literal_text_and_no_delete_action(market_client, buyer_headers, message_path):
    text = '<script>alert("test")</script>\nhttps://example.invalid\tPlease refund this order.'
    response = send(market_client, buyer_headers, message_path, text)
    assert response.status_code == 201 and response.json()["text"] == text
    assert response.headers["content-type"].startswith("application/json")
    assert market_client.delete(
        message_path + "/" + response.json()["id"], headers=buyer_headers
    ).status_code in (404, 405)


@pytest.mark.parametrize(
    "text", ["", "   ", "x" * 2001, 123, True, None, "a\x00b", "a\x1bb", "a\ud800b"]
)
def test_private_validation(market_client, buyer_headers, message_path, text):
    response = market_client.post(
        message_path,
        headers={**buyer_headers, "Content-Type": "application/json"},
        content=json.dumps({"request_id": str(uuid4()), "text": text}, ensure_ascii=True),
    )
    assert response.status_code == 422, response.text
    assert response.headers["cache-control"] == "no-store" and '"input"' not in response.text


@pytest.mark.parametrize(
    "field",
    [
        "sender",
        "sender_account_id",
        "recipient_id",
        "order_id",
        "created_at",
        "paid",
        "attachments",
    ],
)
def test_spoofed_fields_rejected(market_client, buyer_headers, message_path, field):
    response = market_client.post(
        message_path,
        headers=buyer_headers,
        json={
            "request_id": str(uuid4()),
            "text": "A question.",
            field: "PRIVATE_SPOOF",
        },
    )
    assert response.status_code == 422 and "PRIVATE_SPOOF" not in response.text


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "after_sequence=-1", "after_sequence=1001", "after_sequence=word"],
)
def test_pagination_bounds(market_client, buyer_headers, message_path, query):
    response = market_client.get(message_path + "?" + query, headers=buyer_headers)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"


def test_expired_session_cannot_read_or_send(market_client, buyer_headers, message_path):
    with Session(market_client.app.state.engine) as db, db.begin():
        session = db.get(LoginSession, hash_token(buyer_headers["Authorization"].split()[1]))
        session.expires_at = utcnow() - timedelta(seconds=1)
    assert market_client.get(message_path, headers=buyer_headers).status_code == 401
    assert send(market_client, buyer_headers, message_path).status_code == 401
