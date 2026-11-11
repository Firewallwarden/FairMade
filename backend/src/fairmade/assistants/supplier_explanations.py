"""Current deterministic quote eligibility and reasoned explanations; no substitutions."""

from datetime import date
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.assistants.schemas import Evidence, Paragraph
from fairmade.auth import api_error
from fairmade.models import SourcingInput, SupplierComparison
from fairmade.quality.schemas import Rule
from fairmade.suppliers.schemas import SupplierComparisonRequest, SupplierQuoteSnapshot
from fairmade.suppliers.service import COMPARISON_VERSION, compare_suppliers

TITLE = "Current supplier comparison of selected saved quote evidence"
REASONS = {
    "FUTURE_QUOTE": "The observation date is in the future.",
    "STALE_QUOTE": "The quote exceeds the selected maximum age.",
    "EXPIRED_QUOTE": "The quote has expired.",
    "UNAVAILABLE": "The quote reports unavailable supply.",
    "AVAILABILITY_UNKNOWN": "Supply availability is unknown.",
    "TRANSPORT_COST_UNKNOWN": "Transportation cost is unknown.",
    "INCOMPATIBLE_UNITS": "The quantity dimensions are incompatible.",
    "QUALITY_FAILED": "A supplied claim fails a current requirement.",
    "QUALITY_UNKNOWN": "A required claim is missing or cannot be evaluated.",
    "QUALITY_NOT_EVALUATED": "Requirements have not been evaluated.",
    "PURCHASE_LIMIT_EXCEEDED": "The required purchase exceeds the supported package limit.",
    "INSUFFICIENT_AVAILABLE_PACKAGES": "The quote cannot supply enough packages.",
}


def supplier_details(db: Session, product_id: str, report_id: UUID, as_of: date) -> dict:
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
    eligible = [row for row in result.rows if row.eligible_for_cost_comparison]
    excluded = [row for row in result.rows if not row.eligible_for_cost_comparison]
    minimum_purchase = result.lowest_purchase_cost
    minimum_usable = result.lowest_cost_per_usable_unit
    return {
        "report_id": report.id,
        "input_label": sourcing.label,
        "as_of_date": result.as_of_date.isoformat(),
        "rule_revision": sourcing.rule_revision,
        "required_quantity": result.required_quantity.model_dump(mode="json"),
        "eligible": [
            {
                "quote_id": str(row.quote_id),
                "supplier_name": row.details.supplier_name,
                "observed_on": row.details.observed_on.isoformat(),
                "source": row.details.source.model_dump(mode="json"),
                "cost": row.cost.model_dump(mode="json"),
                "quality_status": row.quality.status,
                "checks": [check.model_dump(mode="json") for check in row.quality.checks],
            }
            for row in eligible
        ],
        "excluded": [
            {
                "quote_id": str(row.quote_id),
                "supplier_name": row.details.supplier_name,
                "observed_on": row.details.observed_on.isoformat(),
                "source": row.details.source.model_dump(mode="json"),
                "quality_status": row.quality.status,
                "checks": [check.model_dump(mode="json") for check in row.quality.checks],
                "exclusion_reasons": row.exclusion_reasons,
                "reason_messages": [REASONS[code] for code in row.exclusion_reasons],
                "eligible_for_cost_comparison": False,
                "acceptable_saving": False,
            }
            for row in excluded
        ],
        "excluded_count": len(excluded),
        "lowest_eligible_purchase_cost": str(minimum_purchase)
        if minimum_purchase is not None
        else None,
        "lowest_eligible_usable_cost": str(minimum_usable) if minimum_usable is not None else None,
        "lowest_purchase_quote_ids": [
            str(row.quote_id) for row in eligible if row.cost.purchase_cost == minimum_purchase
        ],
        "lowest_usable_cost_quote_ids": [
            str(row.quote_id) for row in eligible if row.cost.cost_per_usable_unit == minimum_usable
        ],
        "quality_scope": "Current sourcing-input requirements; product constraints remain binding.",
        "policy": (
            "Excluded alternatives are never acceptable savings. "
            "Cost minima apply only to eligible quotes, with ties preserved. "
            "No substitution, certification or overall-quality ranking is authorized."
        ),
        "warnings": result.warnings,
    }


def supplier_context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    data = fact.data
    return {
        "input_label": data["input_label"],
        "eligible_alternatives": [
            {
                "supplier_name": row["supplier_name"],
                "checks": row["checks"],
                "status": "Eligible for this cost comparison only; not certified.",
            }
            for row in data["eligible"]
        ],
        "excluded_alternatives": [
            {
                "supplier_name": row["supplier_name"],
                "checks": row["checks"],
                "reasons": row["reason_messages"],
                "status": "EXCLUDED; never an acceptable saving or recommendation.",
            }
            for row in data["excluded"]
        ],
        "quality_scope": data["quality_scope"],
        "policy": data["policy"],
        "warnings": data["warnings"],
    }


def supplier_statements(fact: Evidence) -> list[Paragraph]:
    if fact.title != TITLE:
        return []
    data = fact.data
    texts = []
    for row in data["eligible"]:
        texts.append(
            f"{row['supplier_name']} (quote {row['quote_id']}): eligible for the selected "
            f"cost comparison. Purchase outlay USD {row['cost']['purchase_cost']}; "
            f"cost per usable {data['required_quantity']['unit']} "
            f"USD {row['cost']['cost_per_usable_unit']}. Claims remain unverified."
        )
    for row in data["excluded"]:
        reasons = " ".join(row["reason_messages"])
        texts.append(
            f"{row['supplier_name']} (quote {row['quote_id']}): EXCLUDED; "
            f"not an acceptable saving. Reasons: {reasons}. No substitution authorized."
        )
    if data["lowest_eligible_purchase_cost"] is not None:
        texts.append(
            f"Lowest eligible purchase outlay: USD {data['lowest_eligible_purchase_cost']}; "
            f"lowest eligible cost per usable {data['required_quantity']['unit']}: "
            f"USD {data['lowest_eligible_usable_cost']}. "
            "These are separate cost objectives, not a quality ranking."
        )
    else:
        texts.append("No eligible quotes; no cost-saving option is inferred.")
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
