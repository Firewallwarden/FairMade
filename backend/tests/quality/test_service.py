"""A match checks unverified supplied values, not actual quality."""

from decimal import localcontext

import pytest

from fairmade.quality.schemas import EvaluationRequest, ReplaceQualityLocks
from fairmade.quality.service import evaluate


def result(lock_body, candidate_body):
    return evaluate(
        ReplaceQualityLocks.model_validate(lock_body).rules,
        EvaluationRequest.model_validate(candidate_body).claims,
    )


def test_all_matching_claims_are_marked_unverified(lock_body, candidate_body):
    checked = result(lock_body, candidate_body)
    assert checked.status == "passed"
    assert all(check.reason_code == "MATCHED" for check in checked.checks)
    assert all("unverified" in check.message for check in checked.checks)
    assert [check.key for check in checked.checks] == [rule["key"] for rule in lock_body["rules"]]


@pytest.mark.parametrize(
    "key,claim,status,reason",
    [
        ("organic_flour", {"type": "boolean", "value": False}, "failed", "BOOLEAN_MISMATCH"),
        ("organic_flour", {"type": "choice", "value": "true"}, "unknown", "TYPE_MISMATCH"),
        ("process", {"type": "choice", "value": "industrial"}, "failed", "CHOICE_NOT_ALLOWED"),
        (
            "process",
            {"type": "choice", "value": "Naturally_leavened"},
            "failed",
            "CHOICE_NOT_ALLOWED",
        ),
        (
            "fermentation",
            {"type": "numeric", "value": "23.999999", "unit": "hour"},
            "failed",
            "BELOW_MINIMUM",
        ),
        (
            "fermentation",
            {"type": "numeric", "value": "48.000001", "unit": "hour"},
            "failed",
            "ABOVE_MAXIMUM",
        ),
        ("fermentation", {"type": "numeric", "value": "24", "unit": "hour"}, "passed", "MATCHED"),
        ("fermentation", {"type": "numeric", "value": "48", "unit": "hour"}, "passed", "MATCHED"),
        (
            "fermentation",
            {"type": "numeric", "value": "1", "unit": "day"},
            "unknown",
            "UNIT_MISMATCH",
        ),
        (
            "fermentation",
            {"type": "numeric", "value": "48", "unit": "Hour"},
            "unknown",
            "UNIT_MISMATCH",
        ),
    ],
)
def test_rule_checks(lock_body, candidate_body, key, claim, status, reason):
    candidate_body["claims"][key] = claim
    checked = result(lock_body, candidate_body)
    check = next(item for item in checked.checks if item.key == key)
    assert (checked.status, check.status, check.reason_code) == (status, status, reason)


@pytest.mark.parametrize("key", ["organic_flour", "process", "fermentation"])
def test_missing_claim_is_unknown(lock_body, candidate_body, key):
    del candidate_body["claims"][key]
    checked = result(lock_body, candidate_body)
    assert checked.status == "unknown"
    check = next(item for item in checked.checks if item.key == key)
    assert (check.status, check.reason_code) == ("unknown", "MISSING_CLAIM")


def test_failure_dominates_unknown_without_hiding_missing_claim(lock_body, candidate_body):
    candidate_body["claims"]["organic_flour"]["value"] = False
    del candidate_body["claims"]["fermentation"]
    checked = result(lock_body, candidate_body)
    assert checked.status == "failed"
    assert {check.status for check in checked.checks} == {"passed", "failed", "unknown"}


def test_no_rules_is_not_a_pass():
    checked = evaluate([], {})
    assert checked.status == "not_evaluated" and checked.checks == []


def test_trimmed_choices_and_units(lock_body, candidate_body):
    candidate_body["claims"]["process"]["value"] = " naturally_leavened "
    candidate_body["claims"]["fermentation"]["unit"] = " hour "
    assert result(lock_body, candidate_body).status == "passed"


@pytest.mark.parametrize(
    "minimum,maximum,value,status",
    [
        ("0", None, "0", "passed"),
        (None, "0", "-0.000001", "passed"),
        ("-2", "-1", "-1", "passed"),
        ("-2", "-1", "-2.000001", "failed"),
        ("1.000001", "1.000001", "1.000001", "passed"),
    ],
)
def test_numeric_bounds_are_exact_and_independent_of_context(minimum, maximum, value, status):
    locks = ReplaceQualityLocks.model_validate(
        {
            "expected_revision": 0,
            "rules": [
                {
                    "key": "measurement",
                    "label": "Synthetic measurement",
                    "type": "numeric",
                    "minimum": minimum,
                    "maximum": maximum,
                    "unit": "custom",
                }
            ],
        }
    )
    candidate = EvaluationRequest.model_validate(
        {
            "candidate_label": "Synthetic claim",
            "expected_revision": 0,
            "claims": {"measurement": {"type": "numeric", "value": value, "unit": "custom"}},
        }
    )
    with localcontext() as context:
        context.prec = 2
        assert evaluate(locks.rules, candidate.claims).status == status


def test_false_can_be_a_mandatory_expected_value():
    locks = ReplaceQualityLocks.model_validate(
        {
            "expected_revision": 0,
            "rules": [
                {
                    "key": "additive",
                    "label": "Demo restriction",
                    "type": "boolean",
                    "expected": False,
                }
            ],
        }
    )
    claims = EvaluationRequest.model_validate(
        {
            "candidate_label": "Synthetic",
            "expected_revision": 0,
            "claims": {"additive": {"type": "boolean", "value": False}},
        }
    ).claims
    assert evaluate(locks.rules, claims).status == "passed"
