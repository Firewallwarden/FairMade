import pytest


@pytest.fixture
def ordered_listing(market_client, market_headers, market_source):
    def create(
        price="12.00",
        title="Public loaf",
        contents=None,
        stock=10,
        quality=None,
        disclose=True,
        location="Exampletown",
        headers=None,
        product_type="sourdough",
    ):
        headers = headers or market_headers
        source = market_source(price=price, title=title, product_type=product_type, headers=headers)
        publication = source["publication"]
        if quality is not None:
            assert (
                market_client.put(
                    source["path"] + "/quality-locks",
                    headers=headers,
                    json={
                        "expected_revision": 0,
                        "rules": [
                            {
                                "key": "spec",
                                "label": "PRIVATE_SPEC_LABEL",
                                "type": "boolean",
                                "expected": True,
                            }
                        ],
                    },
                ).status_code
                == 200
            )
            evaluation = market_client.post(
                source["path"] + "/quality-evaluations",
                headers=headers,
                json={
                    "candidate_label": "PRIVATE_CANDIDATE_LABEL",
                    "expected_revision": 1,
                    "claims": {"spec": {"type": "boolean", "value": quality}},
                },
            )
            assert evaluation.status_code == 201
            review = market_client.post(
                source["path"] + "/pricing-reviews",
                headers=headers,
                json={
                    "pricing_analysis_id": source["analysis"]["id"],
                    "quality_evaluation_ids": [evaluation.json()["id"]],
                },
            )
            assert review.status_code == 201
            draft = market_client.post(
                source["path"] + "/passports",
                headers=headers,
                json={
                    "review_id": review.json()["id"],
                    "title": title,
                    "price": price,
                    "disclosures": {"include_quality_summary": disclose},
                },
            )
            assert draft.status_code == 201
            path = source["path"] + "/passports/" + draft.json()["id"]
            checked = market_client.get(path + "/preview", headers=headers).json()
            published = market_client.post(
                path + "/publish",
                headers=headers,
                json={
                    "expected_revision": checked["revision"],
                    "preview_hash": checked["preview_hash"],
                    "approved": True,
                },
            )
            assert published.status_code == 201
            publication = published.json()
        path = source["path"] + "/listing"
        created = market_client.post(
            path,
            headers=headers,
            json={
                "passport_publication_id": publication["id"],
                "selling_quantity": contents or {"value": "500", "unit": "g"},
                "seller_display_name": "Example bakery",
                "location": location,
            },
        )
        assert created.status_code == 201, created.text
        preview = market_client.get(path + "/preview", headers=headers).json()
        assert (
            market_client.post(
                path + "/activate",
                headers=headers,
                json={
                    "expected_revision": preview["revision"],
                    "preview_hash": preview["preview_hash"],
                    "approved": True,
                },
            ).status_code
            == 200
        )
        if stock is not None:
            assert (
                market_client.put(
                    source["path"] + "/inventory",
                    headers=headers,
                    json={
                        "expected_revision": 0,
                        "selling_unit": source["product"]["selling_unit"],
                        "on_hand": stock,
                    },
                ).status_code
                == 200
            )
        return {**source, "publication": publication, "listing": created.json()}

    return create


@pytest.fixture
def ordered_storefront(market_client, market_headers):
    path = "/api/v1/seller/storefronts"
    created = market_client.post(
        path,
        headers=market_headers,
        json={
            "display_name": "Example bakery",
            "location": "Exampletown",
            "approximate_area": {"label": "Example area", "latitude": "0.00", "longitude": "0.00"},
        },
    )
    assert created.status_code == 201
    identifier = created.json()["id"]
    preview = market_client.get(path + "/" + identifier + "/preview", headers=market_headers).json()
    assert (
        market_client.post(
            path + "/" + identifier + "/publish",
            headers=market_headers,
            json={
                "expected_revision": preview["revision"],
                "preview_hash": preview["preview_hash"],
                "approved": True,
            },
        ).status_code
        == 200
    )
    return identifier
