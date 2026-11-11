"""Owner-selected evidence loading shared by saved reviews and read-only price advice."""

from fastapi.exceptions import RequestValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.comparisons.schemas import ReportResponse
from fairmade.comparisons.service import COMPARISON_VERSION
from fairmade.comparisons.units import named_unit_matches
from fairmade.models import Analysis, PriceComparison, Product, QualityEvaluation, QualityLockSet
from fairmade.quality.schemas import EvaluationResponse
from fairmade.quality.service import EVALUATION_VERSION
from fairmade.reviews.schemas import ReviewRequest
from fairmade.schemas import AnalysisResponse, ProductResponse


def selected_evidence(db: Session, product: Product, body: ReviewRequest) -> dict:
    """Callers establish product ownership before loading its selected immutable sources."""
    analysis = db.scalar(
        select(Analysis).where(
            Analysis.id == str(body.pricing_analysis_id),
            Analysis.product_id == product.id,
        )
    )
    comparison = None
    if body.comparison_report_id:
        comparison = db.scalar(
            select(PriceComparison).where(
                PriceComparison.id == str(body.comparison_report_id),
                PriceComparison.product_id == product.id,
            )
        )
    evaluations = db.scalars(
        select(QualityEvaluation).where(
            QualityEvaluation.product_id == product.id,
            QualityEvaluation.id.in_([str(value) for value in body.quality_evaluation_ids]),
        )
    ).all()
    if (
        analysis is None
        or (body.comparison_report_id and comparison is None)
        or len(evaluations) != len(body.quality_evaluation_ids)
    ):
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    if (
        analysis.calculation_version != "production-economics-v1"
        or analysis.result.get("calculation_version") != "production-economics-v1"
        or (comparison and comparison.comparison_version != COMPARISON_VERSION)
        or any(item.evaluation_version != EVALUATION_VERSION for item in evaluations)
    ):
        raise api_error(
            409, "UNSUPPORTED_EVIDENCE_VERSION", "Selected evidence uses an unsupported version."
        )
    if body.production_unit_quantity and not named_unit_matches(
        analysis.product_snapshot["product_type"],
        body.production_unit_quantity.unit,
    ):
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "production_unit_quantity", "unit"),
                    "msg": "Named units must match the saved pricing product type",
                    "input": body.production_unit_quantity.unit,
                }
            ]
        )
    current = db.get(QualityLockSet, product.id)
    by_id = {item.id: item for item in evaluations}
    evidence = {
        "product": ProductResponse.model_validate(product).model_dump(mode="json"),
        "pricing_analysis": AnalysisResponse.model_validate(analysis).model_dump(mode="json"),
        "quality_lock_set": {
            "revision": current.revision if current else 0,
            "rules": current.rules if current else [],
        },
        "quality_evaluations": [
            EvaluationResponse.model_validate(by_id[str(value)]).model_dump(mode="json")
            for value in body.quality_evaluation_ids
        ],
        "comparison_report": ReportResponse.model_validate(comparison).model_dump(mode="json")
        if comparison
        else None,
    }
    return evidence
