import json
from copy import deepcopy

import pytest

from fairmade.passports.schemas import PublicPassport
from fairmade.publication import public_digest

from .conftest import edit, publish


def test_existing_openapi_draft_type_identity_is_preserved(market_client):
    api = market_client.get("/openapi.json").json()
    schemas = api["components"]["schemas"]
    operation = api["paths"]["/api/v1/products/{product_id}/passports"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DraftContent"
    }
    assert schemas["DraftResponse"]["properties"]["content"] == {
        "$ref": "#/components/schemas/DraftContent"
    }


def test_legacy_public_payload_and_hash_remain_exact_with_private_composition(
    market_client, market_headers, market_record, declaration
):
    source = market_record
    original = source["publication"]
    checked = edit(market_client, market_headers, source, declaration, disclose=False)
    assert checked["payload"] == original["payload"]
    assert checked["preview_hash"] == original["payload_hash"]
    public = market_client.get("/api/v1/passports/" + original["id"])
    assert public.status_code == 200 and public.json()["payload"] == original["payload"]
    assert (
        public_digest(PublicPassport.model_validate(public.json()["payload"]))
        == original["payload_hash"]
    )
    assert "Declared flour" not in public.text and "composition" not in public.json()["payload"]
    private = market_client.get(source["draft_url"], headers=market_headers)
    assert private.headers["cache-control"] == "no-store"
    assert private.json()["content"]["composition"]["items"][0]["label"] == "Declared flour"


def test_composition_requires_exact_preview_approval_and_freezes_published_copy(
    market_client, market_headers, market_record, declaration
):
    source = market_record
    checked = edit(market_client, market_headers, source, declaration)
    assert checked["preview_hash"] != source["publication"]["payload_hash"]
    still_old = market_client.get("/api/v1/passports/" + source["publication"]["id"])
    assert "composition" not in still_old.json()["payload"]
    stale = market_client.post(
        source["draft_url"] + "/publish",
        headers=market_headers,
        json={
            "expected_revision": checked["revision"],
            "preview_hash": source["publication"]["payload_hash"],
            "approved": True,
        },
    )
    assert stale.status_code == 409
    current = publish(market_client, market_headers, source, checked)
    assert current["payload"]["composition"]["items"][0]["declared_quantity"]["value"] == "400"
    edited = deepcopy(declaration)
    edited["items"][0]["label"] = "UNAPPROVED_EDIT"
    edit(market_client, market_headers, source, edited, revision=2)
    public = market_client.get("/api/v1/passports/" + current["id"])
    assert public.status_code == 200 and "UNAPPROVED_EDIT" not in public.text
    assert public.json()["payload"] == current["payload"]


def test_public_listing_includes_only_explicitly_approved_composition(
    market_client, composition_listing
):
    response = market_client.get(
        "/api/v1/marketplace/listings/" + composition_listing["listing_id"]
    )
    assert response.status_code == 200
    disclosed = response.json()["passport"]["payload"]["composition"]
    assert disclosed["completeness"] == "partial"
    assert {row["kind"] for row in disclosed["items"]} == {"ingredient", "packaging"}
    assert "PRIVATE_MARKET" not in response.text and "purchase_cost" not in response.text


@pytest.mark.parametrize(
    "invalid",
    [
        {"items": []},
        {"items": [{"label": "A", "kind": "ingredient"}] * 2},
        {"items": [{"label": "X\ud800", "kind": "ingredient"}]},
        {"items": [{"label": "X", "kind": "ingredient", "reported_role": "a" * 201}]},
        {"items": [{"label": str(index), "kind": "material"} for index in range(21)]},
        {
            "items": [
                {
                    "label": "X",
                    "kind": "ingredient",
                    "declared_quantity": {"value": "1.5", "unit": "egg"},
                }
            ]
        },
        {"items": [{"label": "X", "kind": "ingredient", "secret": "PRIVATE_FAKE_VALUE"}]},
    ],
)
def test_bounded_private_declarations_and_redacted_validation(
    market_client, market_headers, market_record, invalid
):
    response = market_client.put(
        market_record["draft_url"],
        headers={**market_headers, "Content-Type": "application/json"},
        content=json.dumps(
            {
                **market_record["passport_content"],
                "expected_revision": 1,
                "composition": invalid,
                "disclosures": {"include_composition": True},
            },
            ensure_ascii=True,
        ),
    )
    assert response.status_code == 422
    assert "PRIVATE_FAKE_VALUE" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_disclosure_needs_data_and_remains_owner_only(
    market_client, market_headers, buyer_headers, market_account, market_record
):
    body = {
        **market_record["passport_content"],
        "expected_revision": 1,
        "disclosures": {"include_composition": True},
    }
    assert (
        market_client.put(market_record["draft_url"], headers=market_headers, json=body).status_code
        == 422
    )
    assert market_client.get(market_record["draft_url"]).status_code == 401
    assert market_client.get(market_record["draft_url"], headers=buyer_headers).status_code == 403
    other = market_account("other-composition-seller@example.com")
    assert market_client.get(market_record["draft_url"], headers=other).status_code == 404
