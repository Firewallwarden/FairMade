"""Compose private evidence, with owner/access policy independent of assistant transport."""

from datetime import timedelta

from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.marketplace.repository import visible_listings
from fairmade.models import MarketplaceListing
from fairmade.ownership import require_owned_product
from fairmade.pricing.schemas import PricingRequest
from fairmade.pricing.service import calculate
from fairmade.receipts.aggregates import reviewed_totals
from fairmade.seller_insights import domain, repository
from fairmade.seller_insights.schemas import (
    ExpenseComparison,
    InsightOptions,
    InsightReport,
    PriceAssessment,
    Window,
)

NOTICES = [
    "On-demand recorded insights; no autonomous notifications, verified savings or guarantees.",
    "Pricing/production is product-scoped; receipts/materials are seller-wide and unallocated.",
    "Receipts may already be included in production costs; do not deduct them from profit again.",
    "Saved-analysis changes are save-time comparisons, not observed inflation or proven causes.",
    "Complete UTC dates; missing records do not establish zero actual spending or waste.",
    "Only effective uncorrected production reports count; matching labels do not verify contents.",
    "Material quantities stay separate; "
    "no waste valuation, product mapping or avoidable-loss claim.",
    "Reviews are conditional; mandatory quality, safety and ethical requirements remain binding.",
    "No price, stock, recipe, Quality Lock, production, payment or disclosure changes occur.",
]


def assess_price(db: Session, product, analysis) -> PriceAssessment:
    if analysis is None:
        return PriceAssessment(status="missing_analysis")
    if analysis.calculation_version != "production-economics-v1":
        raise api_error(409, "UNSUPPORTED_EVIDENCE_VERSION", "Unsupported analysis version.")
    listing = db.scalar(visible_listings().where(MarketplaceListing.product_id == product.id))
    if listing is None:
        return PriceAssessment(
            status="missing_listing",
            analysis_id=analysis.id,
            analysis_saved_on=analysis.created_at.date(),
        )
    current = listing.public_payload["product"]
    if any(
        snapshot.get("product_type") != product.product_type
        or snapshot.get("selling_unit") != product.selling_unit
        for snapshot in (analysis.product_snapshot, current)
    ):
        return PriceAssessment(
            status="incompatible_basis",
            analysis_id=analysis.id,
            listing_id=listing.id,
            analysis_saved_on=analysis.created_at.date(),
        )
    inputs = PricingRequest.model_validate(
        {**analysis.inputs, "proposed_prices": [listing.public_payload["price"]["amount"]]}
    )
    result = calculate(inputs)
    scenario = result.scenarios[0]
    return PriceAssessment(
        status="assessed",
        analysis_id=analysis.id,
        analysis_saved_on=analysis.created_at.date(),
        listing_id=listing.id,
        listing_revision=listing.published_revision,
        price=scenario.price,
        unit_cost=result.costs.unit_cost,
        break_even_price=result.break_even_price,
        target_price_minimum=result.sustainable_price_range.minimum,
        target_price_maximum=result.sustainable_price_range.maximum,
        profit_per_unit=scenario.profit_per_unit,
        margin=scenario.margin,
        below_break_even=scenario.below_break_even,
        below_target_margin=scenario.below_target_margin,
    )


def load(
    db: Session, account_id: str, product_id: str, options: InsightOptions, analysis_id=None
) -> InsightReport:
    product = require_owned_product(db, account_id, product_id)
    today = utcnow().date()
    split = today - timedelta(days=options.period_days)
    start = split - timedelta(days=options.period_days)
    analysis = repository.analysis(db, product.id, str(analysis_id) if analysis_id else None)
    previous, current = (
        reviewed_totals(db, account_id, start, split),
        reviewed_totals(db, account_id, split, today),
    )
    expense_change = (
        domain.difference(previous.recorded_total, current.recorded_total)
        if (previous.receipt_count and current.receipt_count)
        else domain.difference(None, None)
    )
    materials = repository.bounded(
        domain.material_waste(repository.waste(db, account_id, split, today)), 20
    )
    report = InsightReport(
        product_id=product.id,
        selling_unit=product.selling_unit,
        as_of_date=today,
        current_period=Window(start_date=split, end_date=today),
        previous_period=Window(start_date=start, end_date=split),
        pricing=assess_price(db, product, analysis),
        costs=domain.cost_comparison(
            repository.costs(db, product.id, start, today),
            split,
            product.product_type,
            product.selling_unit,
        ),
        receipts=ExpenseComparison(previous=previous, current=current, difference=expense_change),
        production=domain.production_output(
            repository.production(db, product.id, split, today),
            product.selling_unit,
            product.product_type,
        ),
        materials=materials,
        alerts=[],
        notices=NOTICES,
    )
    report.alerts = domain.alerts(report)
    return report


def report(
    db: Session, account_id: str, product_id: str, options: InsightOptions, analysis_id=None
) -> InsightReport:
    original = load(db, account_id, product_id, options, analysis_id)
    db.expire_all()
    current = load(db, account_id, product_id, options, analysis_id)
    if current != original:
        raise api_error(409, "INSIGHT_EVIDENCE_CHANGED", "Insight evidence changed; try again.")
    return current
