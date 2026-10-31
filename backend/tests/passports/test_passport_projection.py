"""Opt-in disclosure never copies arbitrary private evidence or explanation text."""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fairmade.passports.projection import digest, payload_dict, project
from fairmade.passports.schemas import DraftContent, PublishApproval

SENTINELS = [
    "PRIVATE_PRODUCT_NAME",
    "PRIVATE_PRODUCT_DESCRIPTION",
    "PRIVATE_INGREDIENT_NAME",
    "PRIVATE_WORKER_NAME",
    "PRIVATE_SUPPLIER_NAME",
    "PRIVATE_QUOTE_LABEL",
    "PRIVATE_QUOTE_SOURCE",
    "PRIVATE_RECEIPT",
    "PRIVATE_LOCATION",
    "PRIVATE_QUOTE_NOTES",
]


def test_default_projection_contains_no_costs_or_private_ids(source, content):
    payload = payload_dict(project(source["review"], DraftContent.model_validate(content)))
    encoded = json.dumps(payload)
    assert set(payload) == {
        "passport_version",
        "basis",
        "reviewed_on",
        "product",
        "price",
        "notices",
    }
    assert payload["price"]["amount"] == "17.00"
    assert payload["product"] == {
        "title": content["title"],
        "product_type": "sourdough",
        "selling_unit": "loaf",
    }
    for secret in SENTINELS + [
        source["review"]["id"],
        source["product"]["id"],
        source["analysis_id"],
        source["quality_id"],
        source["observation_id"],
        source["comparison_id"],
    ]:
        assert secret not in encoded
    assert "15.00" not in encoded
    assert payload["basis"] == "seller_reported_unverified"


def test_selected_category_and_labor_do_not_disclose_other_cost_fields(source, content):
    content["disclosures"] = {"cost_categories": ["materials"], "include_labor": True}
    payload = payload_dict(project(source["review"], DraftContent.model_validate(content)))
    assert payload["costs"] == {
        "category_costs_per_unit": {"materials": "5.000000"},
        "labor_per_unit": "3.000000",
    }
    assert "unit_cost" not in payload["costs"]
    assert all(secret not in json.dumps(payload) for secret in SENTINELS)


def test_total_unit_cost_requires_its_own_opt_in(source, content):
    content["disclosures"] = {"include_unit_cost": True}
    payload = payload_dict(project(source["review"], DraftContent.model_validate(content)))
    assert payload["costs"]["unit_cost"] == "10.000000"
    assert payload["costs"]["category_costs_per_unit"] == {}
    assert "labor_per_unit" not in payload["costs"]


def test_quality_summary_keeps_failures_but_hides_candidates(source, content):
    content["disclosures"] = {"include_quality_summary": True}
    payload = payload_dict(project(source["review"], DraftContent.model_validate(content)))
    assert payload["quality_summary"] == {
        "status": "needs_attention",
        "evaluation_count": 1,
        "failed_count": 1,
        "unknown_or_unevaluated_count": 0,
        "outdated_count": 0,
    }
    assert "PRIVATE_SUPPLIER_NAME" not in json.dumps(payload)
    assert "quality_requirements" not in payload


def test_requirements_are_disclosed_only_when_selected(source, content):
    content["disclosures"] = {"include_quality_requirements": True}
    payload = payload_dict(project(source["review"], DraftContent.model_validate(content)))
    assert payload["quality_requirements"][0]["label"] == "PRIVATE_REQUIREMENT_LABEL"
    assert "quality_summary" not in payload
    assert "PRIVATE_SUPPLIER_NAME" not in json.dumps(payload)


def test_market_summary_excludes_raw_quotes_sources_and_identifiers(source, content):
    content["disclosures"] = {"include_market_context": True}
    payload = payload_dict(project(source["review"], DraftContent.model_validate(content)))
    assert payload["market_context"] == {
        "status": "comparable",
        "quantity": {"value": "500", "unit": "g"},
        "included_count": 1,
        "minimum": "8.000000",
        "maximum": "8.000000",
    }
    assert all(secret not in json.dumps(payload) for secret in SENTINELS)
    assert source["observation_id"] not in json.dumps(payload)


def test_hash_only_depends_on_allowlisted_preview(source, content):
    model = DraftContent.model_validate(content)
    before = digest(project(source["review"], model))
    source["review"]["result"]["private_debug"] = "PRIVATE_DEBUG_SECRET"
    source["review"]["evidence_snapshot"]["private_metadata"] = "PRIVATE_EVIDENCE_SECRET"
    assert digest(project(source["review"], model)) == before
    assert len(before) == 64


@pytest.mark.parametrize(
    "policy",
    [
        {"cost_categories": ["unknown"]},
        {"cost_categories": ["materials", "materials"]},
        {"include_labor": 1},
        {"include_unit_cost": "true"},
        {"private_source": True},
    ],
)
def test_policy_is_strict_allowlist(policy):
    with pytest.raises(ValidationError):
        DraftContent.model_validate(
            {
                "review_id": str(uuid4()),
                "title": "Demo",
                "price": "1.00",
                "disclosures": policy,
            }
        )


@pytest.mark.parametrize("price", ["0", "-1", "1.001", 1, True, "NaN", "1000000001"])
def test_price_requires_positive_decimal_cents(price):
    with pytest.raises(ValidationError):
        DraftContent.model_validate({"review_id": str(uuid4()), "title": "Demo", "price": price})


@pytest.mark.parametrize("approved", [False, 1, "true", None])
def test_publication_requires_true_boolean(approved):
    with pytest.raises(ValidationError):
        PublishApproval.model_validate(
            {
                "expected_revision": 1,
                "preview_hash": "a" * 64,
                "approved": approved,
            }
        )
