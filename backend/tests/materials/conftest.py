import pytest


@pytest.fixture
def material(market_client, market_headers):
    response = market_client.post(
        "/api/v1/seller/materials",
        headers=market_headers,
        json={"name": "PRIVATE_FLOUR", "unit": "g", "notes": "PRIVATE_SUPPLY_NOTES"},
    )
    assert response.status_code == 201, response.text
    return response.json()
