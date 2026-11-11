"""Re-evaluate saved quote snapshots against current sourcing-input requirements."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.models import SourcingInput, SupplierComparison
from fairmade.quality.schemas import Rule
from fairmade.suppliers.schemas import (
    SupplierComparisonRequest,
    SupplierComparisonResult,
    SupplierQuoteSnapshot,
)
from fairmade.suppliers.service import COMPARISON_VERSION, compare_suppliers


@dataclass
class CurrentComparison:
    report: SupplierComparison
    sourcing: SourcingInput
    result: SupplierComparisonResult


def current_comparison(
    db: Session, product_id: str, report_id: UUID, as_of: date
) -> CurrentComparison:
    report = db.scalar(
        select(SupplierComparison)
        .join(SourcingInput, SourcingInput.id == SupplierComparison.sourcing_input_id)
        .where(SupplierComparison.id == str(report_id), SourcingInput.product_id == product_id)
    )
    if report is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    if report.comparison_version != COMPARISON_VERSION:
        raise api_error(409, "UNSUPPORTED_EVIDENCE_VERSION", "Unsupported supplier version.")
    sourcing = db.get(SourcingInput, report.sourcing_input_id)
    result = compare_suppliers(
        SupplierComparisonRequest.model_validate(report.request_snapshot),
        [
            SupplierQuoteSnapshot.model_validate({"id": row["quote_id"], "details": row["details"]})
            for row in report.result["rows"]
        ],
        TypeAdapter(list[Rule]).validate_python(sourcing.rules),
        sourcing.rule_revision,
        as_of,
    )
    return CurrentComparison(report, sourcing, result)
