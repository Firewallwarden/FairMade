"""Reject malformed or ambiguous requirements before any evaluation."""

import pytest
from pydantic import ValidationError

from fairmade.quality.schemas import EvaluationRequest, ReplaceQualityLocks


@pytest.mark.parametrize(
    "field,value",
    [
        ("key", ""),
        ("key", "Organic Flour"),
        ("key", "x" * 65),
        ("label", " "),
        ("label", "x" * 201),
        ("expected", "true"),
        ("expected", 1),
        ("expected", None),
        ("type", "text"),
        ("mandatory", False),
    ],
)
def test_boolean_rule_validation(lock_body, field, value):
    lock_body["rules"][0][field] = value
    with pytest.raises(ValidationError):
        ReplaceQualityLocks.model_validate(lock_body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("minimum", 24),
        ("minimum", 24.1),
        ("minimum", True),
        ("minimum", "NaN"),
        ("minimum", "Infinity"),
        ("minimum", "-Infinity"),
        ("minimum", "0.0000001"),
        ("minimum", "-1000000001"),
        ("maximum", "1000000001"),
        ("minimum", "49"),
        ("unit", ""),
        ("unit", " "),
        ("unit", "x" * 201),
    ],
)
def test_numeric_rule_validation(lock_body, field, value):
    lock_body["rules"][2][field] = value
    with pytest.raises(ValidationError):
        ReplaceQualityLocks.model_validate(lock_body)


@pytest.mark.parametrize(
    "allowed", [[], [" "], ["large", "large"], ["large", " large "], ["x" * 201], ["x"] * 101]
)
def test_allowed_choices_are_nonempty_unique_and_bounded(lock_body, allowed):
    lock_body["rules"][1]["allowed_values"] = allowed
    with pytest.raises(ValidationError):
        ReplaceQualityLocks.model_validate(lock_body)


def test_numeric_rule_needs_a_bound(lock_body):
    del lock_body["rules"][2]["minimum"]
    del lock_body["rules"][2]["maximum"]
    with pytest.raises(ValidationError):
        ReplaceQualityLocks.model_validate(lock_body)


def test_rule_keys_must_be_unique(lock_body):
    lock_body["rules"][1]["key"] = lock_body["rules"][0]["key"]
    with pytest.raises(ValidationError):
        ReplaceQualityLocks.model_validate(lock_body)


@pytest.mark.parametrize("revision", [-1, True, 0.5, "0", 2147483647])
def test_revision_is_a_bounded_nonnegative_integer(lock_body, revision):
    lock_body["expected_revision"] = revision
    with pytest.raises(ValidationError):
        ReplaceQualityLocks.model_validate(lock_body)


def test_rule_count_limit(lock_body):
    lock_body["rules"] = [
        {"key": f"k{index}", "label": "Demo", "type": "boolean", "expected": True}
        for index in range(101)
    ]
    with pytest.raises(ValidationError):
        ReplaceQualityLocks.model_validate(lock_body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("value", 24),
        ("value", True),
        ("value", "Infinity"),
        ("value", "0.0000001"),
        ("value", "1000000001"),
        ("unit", " "),
        ("unknown", "ignored"),
    ],
)
def test_numeric_claim_validation(candidate_body, field, value):
    candidate_body["claims"]["fermentation"][field] = value
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(candidate_body)


def test_claim_keys_cannot_collapse_to_the_same_attribute(candidate_body):
    candidate_body["claims"][" organic_flour "] = {"type": "boolean", "value": False}
    with pytest.raises(ValidationError, match="unique after trimming"):
        EvaluationRequest.model_validate(candidate_body)


@pytest.mark.parametrize("value", [1, "true", None])
def test_boolean_claim_is_strict(candidate_body, value):
    candidate_body["claims"]["organic_flour"]["value"] = value
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(candidate_body)


def test_candidate_label_and_claim_count_are_bounded(candidate_body):
    candidate_body["candidate_label"] = " "
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(candidate_body)
    candidate_body["candidate_label"] = "Demo"
    candidate_body["claims"] = {
        f"k{index}": {"type": "boolean", "value": True} for index in range(101)
    }
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(candidate_body)
