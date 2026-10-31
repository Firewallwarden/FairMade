"""Typed rules and claims. Numeric inputs must be decimal JSON strings."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BeforeValidator, Field, StrictBool, model_validator

from fairmade.pricing.schemas import Contract, Label
from fairmade.schemas import UTCResponse

AttributeKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$", max_length=64)]
Revision = Annotated[int, Field(strict=True, ge=0, le=2_147_483_646)]


def require_decimal_string(value: object) -> object:
    if not isinstance(value, str):
        raise ValueError("Numeric values must be decimal JSON strings")
    return value


NumericValue = Annotated[
    Decimal,
    BeforeValidator(require_decimal_string, json_schema_input_type=str),
    Field(ge=-1_000_000_000, le=1_000_000_000, decimal_places=6, allow_inf_nan=False),
]


class RuleBase(Contract):
    key: AttributeKey
    label: Label


class BooleanRule(RuleBase):
    type: Literal["boolean"]
    expected: StrictBool


class ChoiceRule(RuleBase):
    type: Literal["choice"]
    allowed_values: Annotated[list[Label], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def unique_choices(self) -> Self:
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("Allowed choices must be unique after trimming")
        return self


class NumericRule(RuleBase):
    type: Literal["numeric"]
    minimum: NumericValue | None = None
    maximum: NumericValue | None = None
    unit: Label

    @model_validator(mode="after")
    def valid_bounds(self) -> Self:
        if self.minimum is None and self.maximum is None:
            raise ValueError("Provide at least one numeric bound")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Minimum must not exceed maximum")
        return self


Rule = Annotated[BooleanRule | ChoiceRule | NumericRule, Field(discriminator="type")]


class BooleanClaim(Contract):
    type: Literal["boolean"]
    value: StrictBool


class ChoiceClaim(Contract):
    type: Literal["choice"]
    value: Label


class NumericClaim(Contract):
    type: Literal["numeric"]
    value: NumericValue
    unit: Label


Claim = Annotated[BooleanClaim | ChoiceClaim | NumericClaim, Field(discriminator="type")]


class QualityLocks(Contract):
    revision: int
    rules: list[Rule]


class ReplaceQualityLocks(Contract):
    expected_revision: Revision
    rules: Annotated[list[Rule], Field(max_length=100)]

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        keys = [rule.key for rule in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("Rule attribute keys must be unique")
        return self


class EvaluationRequest(Contract):
    candidate_label: Label
    expected_revision: Revision
    claims: Annotated[dict[AttributeKey, Claim], Field(max_length=100)]

    @model_validator(mode="before")
    @classmethod
    def unambiguous_claim_keys(cls, data: object) -> object:
        if isinstance(data, dict) and isinstance(data.get("claims"), dict):
            keys = [key.strip() if isinstance(key, str) else key for key in data["claims"]]
            if len(keys) != len(set(keys)):
                raise ValueError("Claim keys must be unique after trimming")
        return data


CheckStatus = Literal["passed", "failed", "unknown"]
EvaluationStatus = Literal["passed", "failed", "unknown", "not_evaluated"]
ReasonCode = Literal[
    "MATCHED",
    "BOOLEAN_MISMATCH",
    "CHOICE_NOT_ALLOWED",
    "BELOW_MINIMUM",
    "ABOVE_MAXIMUM",
    "MISSING_CLAIM",
    "TYPE_MISMATCH",
    "UNIT_MISMATCH",
]


class QualityCheck(Contract):
    key: str
    label: str
    status: CheckStatus
    reason_code: ReasonCode
    message: str


class EvaluationResult(Contract):
    status: EvaluationStatus
    checks: list[QualityCheck]


class EvaluationSummary(UTCResponse):
    id: UUID
    candidate_label: str
    rule_revision: int
    evaluation_version: str
    status: EvaluationStatus
    created_at: datetime


class EvaluationResponse(EvaluationSummary):
    product_id: UUID
    basis: Literal["seller_reported_unverified"]
    # Historical payloads are returned verbatim, without applying future schemas.
    rules_snapshot: list[dict]
    claims: dict[str, dict]
    checks: list[dict]
