from uuid import uuid4

import pytest


@pytest.fixture
def message_order(market_client, buyer_headers, cart):
    response = market_client.post(
        "/api/v1/orders",
        headers={
            **buyer_headers,
            "Idempotency-Key": str(uuid4()),
        },
        json=cart,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def message_path(message_order):
    return "/api/v1/orders/" + message_order["id"] + "/messages"


def send(client, headers, path, text="A synthetic order question.", request_id=None):
    return client.post(
        path,
        headers=headers,
        json={
            "request_id": request_id or str(uuid4()),
            "text": text,
        },
    )
