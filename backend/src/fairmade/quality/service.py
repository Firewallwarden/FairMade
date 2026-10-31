"""Compare supplied claims exactly; never certify quality or recommend savings."""

from fairmade.quality.schemas import (
    BooleanRule,
    Claim,
    EvaluationResult,
    NumericRule,
    QualityCheck,
    Rule,
)

EVALUATION_VERSION = "quality-evaluation-v1"

MESSAGES = {
    "MATCHED": "The supplied claim matches this rule; the claim is unverified.",
    "BOOLEAN_MISMATCH": "The supplied yes/no claim does not match the required value.",
    "CHOICE_NOT_ALLOWED": "The supplied choice is not in the allowed set.",
    "BELOW_MINIMUM": "The supplied numeric claim is below the inclusive minimum.",
    "ABOVE_MAXIMUM": "The supplied numeric claim is above the inclusive maximum.",
    "MISSING_CLAIM": "No claim was supplied for this mandatory requirement.",
    "TYPE_MISMATCH": "The supplied claim has an incompatible type.",
    "UNIT_MISMATCH": "The supplied unit does not match; no conversion was performed.",
}


def evaluate(rules: list[Rule], claims: dict[str, Claim]) -> EvaluationResult:
    checks = []
    for rule in rules:
        claim = claims.get(rule.key)
        status, reason = "passed", "MATCHED"
        if claim is None:
            status, reason = "unknown", "MISSING_CLAIM"
        elif claim.type != rule.type:
            status, reason = "unknown", "TYPE_MISMATCH"
        elif isinstance(rule, BooleanRule):
            if claim.value != rule.expected:
                status, reason = "failed", "BOOLEAN_MISMATCH"
        elif isinstance(rule, NumericRule):
            if claim.unit != rule.unit:
                status, reason = "unknown", "UNIT_MISMATCH"
            elif rule.minimum is not None and claim.value < rule.minimum:
                status, reason = "failed", "BELOW_MINIMUM"
            elif rule.maximum is not None and claim.value > rule.maximum:
                status, reason = "failed", "ABOVE_MAXIMUM"
        elif claim.value not in rule.allowed_values:
            status, reason = "failed", "CHOICE_NOT_ALLOWED"
        checks.append(
            QualityCheck(
                key=rule.key,
                label=rule.label,
                status=status,
                reason_code=reason,
                message=MESSAGES[reason],
            )
        )
    status = "not_evaluated"
    if checks:
        statuses = {check.status for check in checks}
        if "failed" in statuses:
            status = "failed"
        elif "unknown" in statuses:
            status = "unknown"
        else:
            status = "passed"
    return EvaluationResult(status=status, checks=checks)
