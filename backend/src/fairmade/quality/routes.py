"""Seller-owned rule sets and append-only evaluation history."""

from uuid import UUID

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller, api_error
from fairmade.models import QualityEvaluation, QualityLockSet
from fairmade.products import Limit, Offset, owned_product
from fairmade.quality.schemas import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationSummary,
    QualityLocks,
    ReplaceQualityLocks,
)
from fairmade.quality.service import EVALUATION_VERSION, evaluate
from fairmade.schemas import ErrorResponse, Page

router = APIRouter(
    prefix="/api/v1/products/{product_id}",
    tags=["quality"],
    responses={
        **AUTH_ERRORS,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
CONFLICT = {409: {"model": ErrorResponse}}


def reserve_rule_set(db: DB, product_id: str) -> None:
    # Reserve the SQLite write transaction before reading a revision. Evaluations
    # and replacements serialize so a check and its stored snapshot cannot race.
    # GET never creates a row. Revision zero still represents an unconfigured set.
    db.execute(
        insert(QualityLockSet)
        .values(
            product_id=product_id,
            revision=0,
            rules=[],
        )
        .on_conflict_do_nothing(index_elements=["product_id"])
    )


def revision_conflict():
    return api_error(
        409, "REVISION_CONFLICT", "Quality Locks changed; reload them before retrying."
    )


@router.get("/quality-locks", response_model=QualityLocks)
def get_locks(product_id: UUID, db: DB, seller: VerifiedSeller) -> QualityLocks:
    product = owned_product(db, seller, product_id)
    current = db.get(QualityLockSet, product.id)
    return QualityLocks(
        revision=current.revision if current else 0,
        rules=current.rules if current else [],
    )


@router.put("/quality-locks", response_model=QualityLocks, responses=CONFLICT)
def replace_locks(
    product_id: UUID,
    body: ReplaceQualityLocks,
    db: DB,
    seller: VerifiedSeller,
) -> QualityLocks:
    product = owned_product(db, seller, product_id)
    reserve_rule_set(db, product.id)
    rules = [rule.model_dump(mode="json") for rule in body.rules]
    changed = db.execute(
        update(QualityLockSet)
        .where(
            QualityLockSet.product_id == product.id,
            QualityLockSet.revision == body.expected_revision,
        )
        .values(revision=body.expected_revision + 1, rules=rules)
    )
    if changed.rowcount != 1:
        raise revision_conflict()
    db.commit()
    return QualityLocks(revision=body.expected_revision + 1, rules=body.rules)


@router.post(
    "/quality-evaluations",
    response_model=EvaluationResponse,
    status_code=201,
    responses=CONFLICT,
)
def save_evaluation(
    product_id: UUID,
    body: EvaluationRequest,
    db: DB,
    seller: VerifiedSeller,
) -> QualityEvaluation:
    product = owned_product(db, seller, product_id)
    reserve_rule_set(db, product.id)
    current = db.get(QualityLockSet, product.id)
    if current.revision != body.expected_revision:
        raise revision_conflict()
    rule_set = QualityLocks(revision=current.revision, rules=current.rules)
    unknown_keys = set(body.claims) - {rule.key for rule in rule_set.rules}
    if unknown_keys:
        raise RequestValidationError(
            [
                {
                    "type": "extra_forbidden",
                    "loc": ("body", "claims", key),
                    "msg": "Claim attribute is not defined in the current Quality Locks",
                    "input": body.claims[key].model_dump(mode="json"),
                }
                for key in sorted(unknown_keys)
            ]
        )
    result = evaluate(rule_set.rules, body.claims)
    evaluation = QualityEvaluation(
        product_id=product.id,
        candidate_label=body.candidate_label,
        rule_revision=current.revision,
        rules_snapshot=current.rules,
        claims={key: claim.model_dump(mode="json") for key, claim in body.claims.items()},
        checks=[check.model_dump(mode="json") for check in result.checks],
        status=result.status,
        basis="seller_reported_unverified",
        evaluation_version=EVALUATION_VERSION,
    )
    db.add(evaluation)
    db.commit()
    return evaluation


@router.get("/quality-evaluations", response_model=Page[EvaluationSummary])
def list_evaluations(
    product_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    product = owned_product(db, seller, product_id)
    items = db.scalars(
        select(QualityEvaluation)
        .where(QualityEvaluation.product_id == product.id)
        .order_by(QualityEvaluation.created_at.desc(), QualityEvaluation.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/quality-evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(
    product_id: UUID,
    evaluation_id: UUID,
    db: DB,
    seller: VerifiedSeller,
) -> QualityEvaluation:
    product = owned_product(db, seller, product_id)
    evaluation = db.scalar(
        select(QualityEvaluation).where(
            QualityEvaluation.id == str(evaluation_id),
            QualityEvaluation.product_id == product.id,
        )
    )
    if evaluation is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return evaluation
