from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import AccountRole, Order, OrderMessage

from .conftest import send


def test_rate_bound_and_idempotent_retry_after_limit(
    market_client, buyer_headers, message_path, cart
):
    key = str(uuid4())
    first = send(market_client, buyer_headers, message_path, "First message", key)
    assert first.status_code == 201
    for index in range(9):
        assert (
            send(market_client, buyer_headers, message_path, f"Message {index}").status_code == 201
        )
    blocked = send(market_client, buyer_headers, message_path)
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
    assert blocked.headers["cache-control"] == "no-store"
    another = market_client.post(
        "/api/v1/orders",
        headers={
            **buyer_headers,
            "Idempotency-Key": str(uuid4()),
        },
        json=cart,
    )
    assert another.status_code == 201
    another_path = "/api/v1/orders/" + another.json()["id"] + "/messages"
    assert send(market_client, buyer_headers, another_path).status_code == 429
    retry = send(market_client, buyer_headers, message_path, "First message", key)
    assert retry.status_code == 200 and retry.json() == first.json()
    with Session(market_client.app.state.engine) as db, db.begin():
        for row in db.scalars(select(OrderMessage)):
            row.created_at = utcnow() - timedelta(minutes=2)
    assert send(market_client, buyer_headers, message_path).status_code == 201


def test_full_order_stays_readable_and_retryable(
    market_client, buyer_headers, message_path, monkeypatch
):
    import fairmade.order_messages.service as service

    monkeypatch.setattr(service, "MAX_MESSAGES", 2)
    key = str(uuid4())
    first = send(market_client, buyer_headers, message_path, "First message", key)
    assert first.status_code == 201
    assert send(market_client, buyer_headers, message_path).status_code == 201
    blocked = send(market_client, buyer_headers, message_path)
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "ORDER_MESSAGE_LIMIT"
    assert send(market_client, buyer_headers, message_path, "First message", key).status_code == 200
    assert len(market_client.get(message_path, headers=buyer_headers).json()["items"]) == 2


@pytest.mark.parametrize("identical", [True, False])
def test_concurrent_retries_and_appends_have_unique_sequences(
    market_client,
    buyer_headers,
    message_path,
    identical,
):
    key = str(uuid4())

    def post(index):
        return send(
            market_client,
            buyer_headers,
            message_path,
            "Concurrent message" if identical else f"Concurrent {index}",
            key if identical else str(uuid4()),
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(post, range(4)))
    assert all(response.status_code in (200, 201) for response in responses)
    rows = market_client.get(message_path, headers=buyer_headers).json()["items"]
    assert len(rows) == (1 if identical else 4)
    assert [row["sequence"] for row in rows] == list(range(1, len(rows) + 1))
    assert sum(response.status_code == 201 for response in responses) == (1 if identical else 4)


@pytest.mark.parametrize("change", ["logout", "role"])
def test_revocation_before_append_is_rechecked(
    market_client,
    market_headers,
    message_path,
    message_order,
    monkeypatch,
    change,
):
    from fairmade.order_messages import repository

    original = repository.reserve

    def reserve(db, account_id, order_id):
        if change == "logout":
            assert (
                market_client.post("/api/v1/auth/logout", headers=market_headers).status_code == 204
            )
        else:
            with Session(market_client.app.state.engine) as other, other.begin():
                other.execute(
                    delete(AccountRole).where(
                        AccountRole.account_id == account_id, AccountRole.role == "seller"
                    )
                )
        original(db, account_id, order_id)

    monkeypatch.setattr(repository, "reserve", reserve)
    response = send(market_client, market_headers, message_path)
    assert response.status_code == (401 if change == "logout" else 403)
    with Session(market_client.app.state.engine) as db:
        assert db.scalars(select(OrderMessage)).all() == []


def test_authorization_rechecked_before_read_response(
    market_client,
    market_headers,
    buyer_headers,
    message_path,
    message_order,
    monkeypatch,
):
    from fairmade.order_messages import repository

    original = repository.page
    assert (
        send(market_client, buyer_headers, message_path, "PRIVATE_AFTER_REVOKE").status_code == 201
    )

    def page(db, order_id, after, limit):
        rows = original(db, order_id, after, limit)
        with Session(market_client.app.state.engine) as other, other.begin():
            seller = other.get(Order, message_order["id"]).seller_account_id
            other.execute(
                delete(AccountRole).where(
                    AccountRole.account_id == seller, AccountRole.role == "seller"
                )
            )
        return rows

    monkeypatch.setattr(repository, "page", page)
    response = market_client.get(message_path, headers=market_headers)
    assert response.status_code == 403 and "PRIVATE_AFTER_REVOKE" not in response.text


def test_failed_commit_rolls_back_send_and_sequence(
    market_client, buyer_headers, message_path, monkeypatch
):
    from sqlalchemy.orm import Session as SessionClass

    original = SessionClass.commit

    def fail(self):
        raise RuntimeError("Synthetic commit failure")

    with monkeypatch.context() as change:
        change.setattr(SessionClass, "commit", fail)
        with pytest.raises(RuntimeError, match="Synthetic commit failure"):
            send(market_client, buyer_headers, message_path)
    assert SessionClass.commit is original
    assert market_client.get(message_path, headers=buyer_headers).json()["items"] == []
    assert send(market_client, buyer_headers, message_path).json()["sequence"] == 1


def test_windows_newlines_are_canonical_for_retries(market_client, buyer_headers, message_path):
    key = str(uuid4())
    first = send(market_client, buyer_headers, message_path, "First\r\nSecond\rThird", key)
    retry = send(market_client, buyer_headers, message_path, "First\nSecond\nThird", key)
    assert first.status_code == 201 and retry.status_code == 200
    assert first.json() == retry.json()


def test_raw_input_cap_and_unicode_character_boundary(market_client, buyer_headers, message_path):
    padded = send(market_client, buyer_headers, message_path, " " * 4001 + "hello")
    assert padded.status_code == 422
    text = "\U0001f600" * 2000
    message = send(market_client, buyer_headers, message_path, text)
    assert message.status_code == 201 and message.json()["text"] == text
