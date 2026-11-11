"""Owned aggregate sales and bounded nominal cost history, independent of model arithmetic."""

import re
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.assistants.expenses import expense_evidence
from fairmade.assistants.schemas import Evidence, HistoryPeriod, Paragraph, SellerQuestion
from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.models import Analysis
from fairmade.pricing.schemas import PricingResponse
from fairmade.sales import repository as sales_repository
from fairmade.sales.service import summarize

SALES_TITLE = "Private seller-wide sandbox sales history"
COST_TITLE = "Selected product saved cost history"
MAX_ANALYSES = 25
HISTORY_WORDS = re.compile(
    r"\b(sales?|revenue|sold|refunds?|history|historical|trends?|changed|"
    r"increased|decreased|expenses?|spend|spent|spending|receipts?|last year|last month|this month|"
    r"yesterday|today|last week|last \d+ days)\b",
    re.IGNORECASE,
)


def period_for(body: SellerQuestion) -> HistoryPeriod | None:
    if body.history_period is not None:
        return body.history_period
    if not HISTORY_WORDS.search(body.question):
        return None
    today = utcnow().date()
    text = body.question.casefold()
    end = today + timedelta(days=1)
    if re.search(r"\b(?:19|20)\d{2}\b|next month|last quarter|forecast", text):
        raise api_error(422, "INVALID_PERIOD", "Supply history_period for calendar date questions.")
    if "last year" in text:
        end = today.replace(month=1, day=1)
        start = end.replace(year=end.year - 1)
    elif "yesterday" in text:
        end = today
        start = today - timedelta(days=1)
    elif "today" in text:
        start = today
    elif "last month" in text:
        end = today.replace(day=1)
        start = (end - timedelta(days=1)).replace(day=1)
    elif "this month" in text:
        start = today.replace(day=1)
    else:
        match = re.search(r"\blast (\d+) days\b", text)
        days = int(match.group(1)) if match else (7 if "last week" in text else 30)
        if not 1 <= days <= 366:
            raise api_error(422, "INVALID_PERIOD", "Use a history period of 1-366 days.")
        start = end - timedelta(days=days)
    return HistoryPeriod(start_date=start, end_date=end)


def cost_history(db: Session, product_id: str, period: HistoryPeriod) -> dict:
    rows = db.scalars(
        select(Analysis)
        .where(
            Analysis.product_id == product_id,
            Analysis.created_at >= datetime.combine(period.start_date, time.min),
            Analysis.created_at < datetime.combine(period.end_date, time.min),
        )
        .order_by(Analysis.created_at, Analysis.id)
        .limit(MAX_ANALYSES + 1)
    ).all()
    if len(rows) > MAX_ANALYSES:
        raise api_error(409, "ASSISTANT_HISTORY_TOO_LARGE", "Narrow the cost-history period.")
    if any(row.calculation_version != "production-economics-v1" for row in rows):
        raise api_error(409, "UNSUPPORTED_EVIDENCE_VERSION", "Unsupported history version.")
    observations = []
    with localcontext() as context:
        context.prec = 60
        for row in rows:
            result = PricingResponse.model_validate(row.result)
            observations.append(
                {
                    "analysis_id": row.id,
                    "saved_at": row.created_at.isoformat(),
                    "selling_unit": row.product_snapshot["selling_unit"],
                    "product_type": row.product_snapshot["product_type"],
                    "unit_cost": str(result.costs.unit_cost),
                    "components_per_unit": {
                        **{
                            key: str(
                                (value / Decimal(row.inputs["sellable_units"])).quantize(
                                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                                )
                            )
                            for key, value in result.costs.category_totals.items()
                        },
                        "labor": str(
                            (
                                result.costs.labor_total / Decimal(row.inputs["sellable_units"])
                            ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                        ),
                    },
                }
            )
        bases = {(row["selling_unit"], row["product_type"]) for row in observations}
        comparable = len(observations) >= 2 and len(bases) == 1
        delta = None
        changes = {}
        if comparable:
            first, last = observations[0], observations[-1]
            delta = str(Decimal(last["unit_cost"]) - Decimal(first["unit_cost"]))
            changes = {
                key: str(
                    Decimal(last["components_per_unit"][key])
                    - Decimal(first["components_per_unit"][key])
                )
                for key in first["components_per_unit"]
            }
    return {
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "observations": observations,
        "nominal_basis_comparable": comparable,
        "latest_minus_earliest_unit_cost": delta,
        "component_changes_per_unit": changes,
        "limitations": [
            "Save-time history, not observed expense dates or seasonal forecasting.",
            "Not an expense ledger or proof of actual procurement spending.",
            "Matching product type and unit labels do not verify equal contents or quality.",
            "Changed recipes, allocations, yields or inputs can explain nominal differences.",
        ],
    }


def history_evidence(
    db: Session,
    account_id: str,
    body: SellerQuestion,
    facts: list[Evidence],
) -> None:
    period = period_for(body)
    if period is None:
        return
    expense_evidence(db, account_id, period, facts)
    records = sales_repository.summary_records(db, account_id, period.start_date, period.end_date)
    if len(records) > sales_repository.MAX_SUMMARY_ORDERS:
        raise api_error(409, "REPORT_TOO_LARGE", "Narrow the sales period.")
    summary = summarize(records, period.start_date, period.end_date, utcnow())
    facts.append(
        Evidence(
            key=f"e{len(facts) + 1}",
            title=SALES_TITLE,
            basis="verified_sandbox_captures_and_unverified_cost_estimates",
            data=summary.model_dump(mode="json", exclude={"generated_at"}),
        )
    )
    facts.append(
        Evidence(
            key=f"e{len(facts) + 1}",
            title=COST_TITLE,
            basis="seller_supplied_unverified",
            data=cost_history(db, str(body.product_id), period),
        )
    )


def history_context(fact: Evidence) -> dict | None:
    data = fact.data
    if fact.title == SALES_TITLE:
        if data["sales_count"] == 0:
            return {
                "status": "No verified completed sandbox captures in the selected period.",
                "policy": (
                    "Do not describe products as sold or income as earned. "
                    "Zero report totals mean no recorded qualifying captures, "
                    "not proof of the seller's real business income."
                ),
            }
        return {
            "scope": "Seller-wide verified sandbox capture cohort, not live earnings or payouts.",
            "profit_available": data["estimated_profit"] is not None,
            "cost_coverage_complete": data["missing_cost_count"] == 0,
            "fee_coverage_complete": data["missing_fee_count"] == 0,
            "refunds_unresolved": data["unresolved_refund_count"] > 0,
            "completed_refunds_included": True,
            "policy": "Explain coverage; exact financial outcomes are in calculated facts.",
            "warnings": data["warnings"],
        }
    if fact.title == COST_TITLE:
        return {
            "has_history": bool(data["observations"]),
            "nominal_basis_comparable": data["nominal_basis_comparable"],
            "increased_components": [
                key
                for key, delta in data["component_changes_per_unit"].items()
                if Decimal(delta) > 0
            ],
            "policy": "Recorded component differences are not proven causes or seasonal effects.",
            "limitations": data["limitations"],
        }
    return None


def history_statements(fact: Evidence) -> list[Paragraph]:
    data = fact.data
    texts = []
    if fact.title == SALES_TITLE:
        profit = data["estimated_profit"]
        profit_text = f"USD {profit}" if profit is not None else "unavailable: incomplete evidence"
        texts.append(
            f"Seller-wide sandbox captures from {data['start_date']} to "
            f"{data['end_date']} (exclusive): {data['sales_count']} sales; "
            f"gross USD {data['gross_sales']}; completed refunds USD {data['completed_refunds']}. "
            f"Estimated profit: {profit_text}. Not live earnings or seller payouts."
        )
    elif fact.title == COST_TITLE:
        texts.append(
            f"Selected product saved analyses in the period: {len(data['observations'])}. "
            "These are save-time snapshots of unverified inputs."
        )
        if data["nominal_basis_comparable"]:
            texts.append(
                f"Latest minus earliest nominal unit cost: USD "
                f"{data['latest_minus_earliest_unit_cost']}. "
                "Matching labels do not establish equal contents, quality or expense causation."
            )
        else:
            texts.append("No cost difference: too few analyses or incompatible unit labels.")
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
