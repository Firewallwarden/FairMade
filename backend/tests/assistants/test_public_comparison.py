import pytest


@pytest.mark.parametrize(
    "second_unit,compatible,expected",
    [
        ("kg", True, "14.000000"),
        ("loaf", False, None),
    ],
)
def test_public_price_comparison_is_calculated_only_for_compatible_bases(
    market_client,
    market_headers,
    market_source,
    ai_gateway,
    second_unit,
    compatible,
    expected,
):
    ids = []
    for quantity, unit, price in (("500", "g", "17.00"), ("1", second_unit, "20.00")):
        source = market_source(price=price)
        path = source["path"] + "/listing"
        created = market_client.post(
            path,
            headers=market_headers,
            json={
                "passport_publication_id": source["publication"]["id"],
                "seller_display_name": "Synthetic bakery",
                "selling_quantity": {"value": quantity, "unit": unit},
            },
        )
        assert created.status_code == 201
        preview = market_client.get(path + "/preview", headers=market_headers).json()
        assert (
            market_client.post(
                path + "/activate",
                headers=market_headers,
                json={
                    "approved": True,
                    "expected_revision": preview["revision"],
                    "preview_hash": preview["preview_hash"],
                },
            ).status_code
            == 200
        )
        ids.append(created.json()["id"])
    response = market_client.post(
        "/api/v1/assistants/buyer",
        headers=market_headers,
        json={
            "question": "Compare unit prices without guessing product quality.",
            "listing_ids": ids,
        },
    )
    assert response.status_code == 200, response.text
    pair = response.json()["evidence"][-2]["data"]["pairs"][0]
    assert pair["left_listing_id"] == ids[0] and pair["right_listing_id"] == ids[1]
    assert pair["compatible_price_basis"] is compatible
    assert pair["left_minus_right_unit_price"] == expected
