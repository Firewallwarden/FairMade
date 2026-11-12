"""Current owner-only review report; no ordering, recipe mutation or automatic substitution."""

from uuid import UUID

from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.evidence import today
from fairmade.ownership import require_owned_product
from fairmade.supplier_recommendations import domain
from fairmade.supplier_recommendations.schemas import RecommendationOptions, RecommendationReport
from fairmade.suppliers.current import current_comparison

NOTICES = [
    "Only the saved report's quotes are considered, using current sourcing-input requirements.",
    "Mandatory failure, unknown quality, stale/expired quotes, unavailable supply and unknown "
    "transport exclude a quote regardless of optional preferences or price.",
    "Optional matches describe supplied unverified claims, not verified quality or certifications.",
    "Unknown optional claims remain unknown; a missing match is not a low actual quality grade.",
    "Savings selects minimum objective cost with all ties; quality uses ordered preference "
    "matches then minimum cost; balanced returns non-dominated cost/preference tradeoffs.",
    "Purchase outlay and rounded cost per usable unit are separate objectives; "
    "minimum outlay is not a guaranteed saving against a current supplier.",
    "Selection is for input review only. Finished-product impact and all product Quality Locks "
    "remain to be checked; no substitution, recipe, stock or pricing change is authorized.",
    "No overall quality/value/fairness score, subjective weight "
    "or verified supplier rating is invented.",
]


def load(
    db: Session,
    account_id: str,
    product_id: str,
    report_id: UUID,
    options: RecommendationOptions,
) -> RecommendationReport:
    product = require_owned_product(db, account_id, product_id)
    current = current_comparison(db, product.id, report_id, today())
    rows = [domain.projection(row, options) for row in current.result.rows]
    selected = domain.select(rows, options)
    notices = NOTICES + current.result.warnings
    if not options.preferences:
        notices += ["No optional preferences were supplied; all modes reduce to minimum cost ties."]
    elif not any(any(row.preference_matches) for row in rows if row.eligible):
        notices += [
            "No eligible quote has a known optional preference match; "
            "selection reflects cost among unmatched claims, not established quality."
        ]
    if not selected:
        notices += ["No eligible input-review candidate; no substitution or saving is inferred."]
    return RecommendationReport(
        product_id=product.id,
        supplier_report_id=current.report.id,
        sourcing_input_id=current.sourcing.id,
        input_label=current.sourcing.label,
        rule_revision=current.result.rule_revision,
        as_of_date=current.result.as_of_date,
        required_quantity=current.result.required_quantity,
        options=options,
        rows=rows,
        selected_quote_ids=selected,
        notices=notices,
    )


def recommend(
    db: Session, account_id: str, product_id: str, report_id: UUID, options: RecommendationOptions
) -> RecommendationReport:
    original = load(db, account_id, product_id, report_id, options)
    db.expire_all()
    current = load(db, account_id, product_id, report_id, options)
    if current != original:
        raise api_error(
            409, "SUPPLIER_RECOMMENDATION_CHANGED", "Supplier evidence changed; try again."
        )
    return current
