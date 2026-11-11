import json
from pathlib import Path

import pytest

from fairmade.composition.integration import TITLE


class CompositionGateway:
    def __init__(self):
        self.calls = []
        self.after = None

    def complete(self, messages, schema):
        self.calls.append(messages)
        if "proposed_prices" in schema["properties"]:
            return {"proposed_prices": []}
        if self.after:
            self.after()
        facts = json.loads(messages[-1]["content"])["EVIDENCE"]
        fact = next(
            (
                row
                for row in facts
                if row["title"] in (TITLE, "Currently approved public listing and Passport")
            ),
            facts[0],
        )
        return {
            "paragraphs": [
                {
                    "text": "Seller declarations remain unverified and do not establish safety.",
                    "evidence_keys": [fact["key"]],
                }
            ]
        }


@pytest.fixture
def composition_gateway(market_client):
    gateway = CompositionGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def declaration():
    return {
        "completeness": "partial",
        "items": [
            {
                "label": "Declared flour",
                "kind": "ingredient",
                "reported_role": "Seller's structure claim",
                "reported_specification": "Seller-reported flour grade",
                "declared_quantity": {
                    "value": "400",
                    "unit": "g",
                },
            },
            {"label": "Paper wrap", "kind": "packaging", "reported_role": "Packaging declaration"},
        ],
    }


@pytest.fixture
def recipe_input_body():
    path = Path(__file__).parents[2] / "examples/recipes/sourdough.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["ingredients"][0]["label"] = "PRIVATE_RECIPE_INPUT"
    body["instructions"] = "PRIVATE_RECIPE_INSTRUCTIONS"
    return body


def edit(client, headers, source, declaration, *, disclose=True, revision=1):
    response = client.put(
        source["draft_url"],
        headers=headers,
        json={
            **source["passport_content"],
            "expected_revision": revision,
            "composition": declaration,
            "disclosures": {"include_composition": disclose},
        },
    )
    assert response.status_code == 200, response.text
    return client.get(source["draft_url"] + "/preview", headers=headers).json()


def publish(client, headers, source, preview):
    response = client.post(
        source["draft_url"] + "/publish",
        headers=headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def composition_listing(market_client, market_headers, market_record, declaration):
    preview = edit(market_client, market_headers, market_record, declaration)
    publication = publish(market_client, market_headers, market_record, preview)
    path = market_record["path"] + "/listing"
    created = market_client.post(
        path,
        headers=market_headers,
        json={
            "passport_publication_id": publication["id"],
            "seller_display_name": "Example bakery",
            "selling_quantity": {"value": "1", "unit": "loaf"},
        },
    )
    assert created.status_code == 201
    checked = market_client.get(path + "/preview", headers=market_headers).json()
    activated = market_client.post(
        path + "/activate",
        headers=market_headers,
        json={
            "expected_revision": checked["revision"],
            "preview_hash": checked["preview_hash"],
            "approved": True,
        },
    )
    assert activated.status_code == 200
    return {
        **market_record,
        "listing_id": created.json()["id"],
        "composition_publication": publication,
    }
