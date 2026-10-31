"""A review explains selected evidence without making a price or certification decision."""

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fairmade.reviews.schemas import ReviewRequest
from fairmade.reviews.service import build_review

REVIEW_DATE = date(2026, 1, 31)


def selection(evidence, mapped=True):
    return ReviewRequest.model_validate(
        {
            "pricing_analysis_id": evidence["pricing_analysis"]["id"],
            "comparison_report_id": evidence["comparison_report"]["id"]
            if evidence["comparison_report"]
            else None,
            "quality_evaluation_ids": [item["id"] for item in evidence["quality_evaluations"]],
            "production_unit_quantity": {"value": "500", "unit": "g"} if mapped else None,
        }
    )


def test_explicit_mapping_links_prices_without_recommending_a_price(evidence):
    checked = build_review(selection(evidence), evidence, REVIEW_DATE)
    market = checked["market_context"]
    assert market["status"] == "comparable"
    assert market["reassessed_comparison"]["selected_price_range"]["minimum"] == "8.000000"
    assert market["price_assessments"][0] == {
        "metric": "break_even_price",
        "price": "10.57",
        "displayed_range_relation": "above",
        "scenario_index": None,
    }
    assert checked["economics"] == evidence["pricing_analysis"]["result"]
    assert checked["quality"]["status"] == "claims_match_unverified"
    assert "QUALITY_NOT_VERIFIED" in checked["warnings"]
    assert "QUALITY_EVIDENCE_NOT_LINKED_TO_MARKET_QUOTES" in checked["warnings"]
    assert "LOSS_MAKING_SCENARIOS" in checked["warnings"]
    assert "NO_OBJECTIVE_FAIRNESS_VERDICT" in checked["warnings"]
    assert any(item["code"] == "DECISION_BOUNDARY" for item in checked["explanations"])


def test_no_mapping_does_not_compare_per_loaf_against_per_100g(evidence):
    checked = build_review(selection(evidence, mapped=False), evidence, REVIEW_DATE)
    market = checked["market_context"]
    assert market["status"] == "basis_missing"
    assert market["price_assessments"] == []
    assert market["reassessed_comparison"]["selected_price_range"]["minimum"] == "1.600000"
    assert "PRICE_BASIS_NOT_LINKED" in checked["warnings"]


def test_incompatible_mapping_does_not_invent_a_loaf_weight(evidence):
    raw = selection(evidence).model_dump(mode="json")
    raw["production_unit_quantity"] = {"value": "1", "unit": "loaf"}
    request = ReviewRequest.model_validate(raw)
    checked = build_review(request, evidence, REVIEW_DATE)
    assert checked["market_context"]["status"] == "no_comparable_evidence"
    assert checked["market_context"]["price_assessments"] == []
    assert checked["market_context"]["reassessed_comparison"]["rows"][0]["normalized_price"] is None


@pytest.mark.parametrize("status", ["failed", "unknown", "not_evaluated"])
def test_failed_or_missing_quality_information_requires_attention(evidence, status):
    evidence["quality_evaluations"][0]["status"] = status
    checked = build_review(selection(evidence), evidence, REVIEW_DATE)
    assert checked["quality"]["status"] == "needs_attention"
    expected = (
        "MANDATORY_QUALITY_REQUIREMENT_FAILED"
        if status == "failed"
        else "QUALITY_COMPLIANCE_NOT_ESTABLISHED"
    )
    assert expected in checked["warnings"]
    if status == "failed":
        assert any(
            "Do not treat it as an acceptable saving" in item["message"]
            for item in checked["explanations"]
        )


@pytest.mark.parametrize("changed", ["revision", "rules"])
def test_old_quality_checks_cannot_establish_current_compliance(evidence, changed):
    if changed == "revision":
        evidence["quality_lock_set"]["revision"] += 1
    else:
        evidence["quality_lock_set"]["rules"] = []
    checked = build_review(selection(evidence), evidence, REVIEW_DATE)
    assert checked["quality"]["status"] == "needs_attention"
    assert checked["quality"]["evaluations"][0]["applies_to_review_rules"] is False
    assert "QUALITY_EVALUATION_OUTDATED" in checked["warnings"]


def test_quote_freshness_is_reassessed_without_changing_source_report(evidence):
    original = evidence["comparison_report"]["result"]["selected_price_range"].copy()
    checked = build_review(selection(evidence), evidence, date(2026, 3, 3))
    assert checked["market_context"]["status"] == "no_comparable_evidence"
    assert checked["market_context"]["price_assessments"] == []
    assert checked["market_context"]["reassessed_comparison"]["rows"][0]["stale"] is True
    assert evidence["comparison_report"]["result"]["selected_price_range"] == original


def test_saved_product_type_mismatch_prevents_numeric_comparison(evidence):
    evidence["comparison_report"]["product_snapshot"]["product_type"] = "eggs"
    checked = build_review(selection(evidence), evidence, REVIEW_DATE)
    assert checked["market_context"]["status"] == "product_type_mismatch"
    assert checked["market_context"]["price_assessments"] == []


def test_missing_evidence_is_explicit_not_a_pass(evidence):
    evidence["quality_evaluations"] = []
    evidence["quality_lock_set"] = {"revision": 0, "rules": []}
    evidence["comparison_report"] = None
    checked = build_review(selection(evidence, mapped=False), evidence, REVIEW_DATE)
    assert checked["quality"]["status"] == checked["market_context"]["status"] == "not_provided"
    assert {
        "QUALITY_EVIDENCE_MISSING",
        "QUALITY_REQUIREMENTS_NOT_CONFIGURED",
        "COMPARISON_EVIDENCE_MISSING",
    } <= set(checked["warnings"])


def test_changed_product_metadata_is_flagged(evidence):
    evidence["product"] = {**evidence["product"], "name": "Renamed"}
    checked = build_review(selection(evidence), evidence, REVIEW_DATE)
    assert "PRODUCT_CHANGED_SINCE_PRICING" in checked["warnings"]


def test_price_relations_include_below_and_equal(evidence):
    request = selection(evidence)
    evidence["comparison_report"]["result"]["rows"][0]["details"]["price"] = "15"
    checked = build_review(request, evidence, REVIEW_DATE)
    assessments = checked["market_context"]["price_assessments"]
    assert assessments[0]["displayed_range_relation"] == "below"
    assert assessments[-1]["displayed_range_relation"] == "within"
    assert assessments[-1]["scenario_index"] == 1


def test_selection_is_bounded_and_does_not_accept_computed_facts():
    identifier = str(uuid4())
    for extra in (
        {"quality_evaluation_ids": [identifier, identifier]},
        {"quality_evaluation_ids": [str(uuid4()) for _index in range(101)]},
        {"production_unit_quantity": {"value": "500", "unit": "g"}},
        {"result": {"fair": True}},
        {"basis": "verified"},
        {"product_id": str(uuid4())},
    ):
        with pytest.raises(ValidationError):
            ReviewRequest.model_validate({"pricing_analysis_id": identifier, **extra})
