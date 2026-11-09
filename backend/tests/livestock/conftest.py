from datetime import date
from uuid import uuid4

import pytest

BASE = "/api/v1/seller/livestock"


@pytest.fixture
def livestock_group_body():
    return {
        "request_id": str(uuid4()),
        "occurred_on": date.today().isoformat(),
        "reason": "Synthetic initial observation",
        "name": "PRIVATE_LAYING_FLOCK",
        "species": "Chicken",
        "reported_headcount": 30,
        "headcount_on": date.today().isoformat(),
    }


@pytest.fixture
def livestock_animal_body():
    return {
        "request_id": str(uuid4()),
        "occurred_on": date.today().isoformat(),
        "reason": "Synthetic individual registration",
        "identifier": "PRIVATE_HEN_001",
        "name": "Demo hen",
        "species": "chicken",
        "sex": "female",
        "born_on": "2025-03-01",
        "acquired_on": "2025-04-01",
    }


@pytest.fixture
def livestock_group(market_client, market_headers, livestock_group_body):
    response = market_client.post(
        BASE + "/groups", headers=market_headers, json=livestock_group_body
    )
    assert response.status_code == 201, response.text
    return response.json()["after"]


@pytest.fixture
def livestock_animal(market_client, market_headers, livestock_group, livestock_animal_body):
    response = market_client.post(
        BASE + "/animals",
        headers=market_headers,
        json={
            **livestock_animal_body,
            "group_id": livestock_group["id"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["after"]


@pytest.fixture
def livestock_product(market_client, market_headers):
    response = market_client.post(
        "/api/v1/products",
        headers=market_headers,
        json={
            "name": "Synthetic eggs",
            "product_type": "eggs",
            "selling_unit": "dozen",
        },
    )
    assert response.status_code == 201
    return "/api/v1/products/" + response.json()["id"]


@pytest.fixture
def livestock_production_body():
    return {
        "request_id": str(uuid4()),
        "label": "Synthetic egg period",
        "kind": "production_period",
        "started_on": "2025-05-01",
        "completed_on": "2025-05-07",
        "selling_unit": "dozen",
        "total_units": 15,
        "sellable_units": 14,
        "currency": "USD",
        "costs": [{"label": "Manually allocated feed", "category": "materials", "amount": "30"}],
        "labor": [{"label": "Care", "hours": "2", "hourly_rate": "15"}],
    }
