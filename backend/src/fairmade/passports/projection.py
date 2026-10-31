"""Pure allowlist projection. Never forward private review dictionaries."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from pydantic import TypeAdapter

from fairmade.passports.schemas import (
    DisclosedCosts,
    DraftContent,
    PublicMarketContext,
    PublicPassport,
    PublicPrice,
    PublicProduct,
    PublicQualitySummary,
)
from fairmade.publication import public_digest
from fairmade.quality.schemas import Rule

NOTICES = [
    "Seller-reported inputs and claims are unverified.",
    "The seller approved this disclosure; it is not a certification or objective fairness verdict.",
    "Some cost and evidence details may be undisclosed.",
    "This is a historical snapshot, not a guarantee of current costs or availability.",
]
DETAIL = Decimal("0.000001")


def _costs(review: dict, content: DraftContent) -> DisclosedCosts | None:
    policy = content.disclosures
    if not (policy.cost_categories or policy.include_labor or policy.include_unit_cost):
        return None
    costs = review["result"]["economics"]["costs"]
    yield_count = review["evidence_snapshot"]["pricing_analysis"]["inputs"]["sellable_units"]
    with localcontext() as context:
        context.prec = 60
        categories = {
            category: (Decimal(costs["category_totals"][category]) / yield_count).quantize(
                DETAIL, rounding=ROUND_HALF_UP
            )
            for category in policy.cost_categories
        }
        labor = (
            (Decimal(costs["labor_total"]) / yield_count).quantize(
                DETAIL,
                rounding=ROUND_HALF_UP,
            )
            if policy.include_labor
            else None
        )
    return DisclosedCosts(
        category_costs_per_unit=categories,
        labor_per_unit=labor,
        unit_cost=Decimal(costs["unit_cost"]) if policy.include_unit_cost else None,
    )


def _quality_summary(review: dict) -> PublicQualitySummary:
    quality = review["result"]["quality"]
    evaluations = quality["evaluations"]
    return PublicQualitySummary(
        status=quality["status"],
        evaluation_count=len(evaluations),
        failed_count=sum(item["saved_status"] == "failed" for item in evaluations),
        unknown_or_unevaluated_count=sum(
            item["saved_status"] in ("unknown", "not_evaluated") for item in evaluations
        ),
        outdated_count=sum(not item["applies_to_review_rules"] for item in evaluations),
    )


def _market_context(review: dict) -> PublicMarketContext:
    context = review["result"]["market_context"]
    comparison = context["reassessed_comparison"]
    if comparison is None:
        return PublicMarketContext(status=context["status"], included_count=0)
    bounds = comparison["selected_price_range"]
    return PublicMarketContext(
        status=context["status"],
        quantity=comparison["target_quantity"],
        included_count=bounds["included_count"],
        minimum=bounds["minimum"],
        maximum=bounds["maximum"],
    )


def project(review: dict, content: DraftContent) -> PublicPassport:
    source = review["evidence_snapshot"]["pricing_analysis"]["product_snapshot"]
    policy = content.disclosures
    requirements = None
    if policy.include_quality_requirements:
        requirements = TypeAdapter(list[Rule]).validate_python(
            review["evidence_snapshot"]["quality_lock_set"]["rules"],
        )
    notices = list(NOTICES)
    if policy.include_quality_summary or policy.include_quality_requirements:
        notices.append(
            "Requirements are seller-defined; matching claims are not independently verified."
        )
    if policy.include_market_context:
        notices.append(
            "Selected nominal quote context does not establish quality equivalence "
            "or local-market fairness; "
            "taxes, shipping and discounts are not reconciled. Quantity bases may differ.",
        )
    with localcontext() as context:
        context.prec = 60
        price = content.price.quantize(Decimal("0.01"))
    return PublicPassport(
        reviewed_on=review["reviewed_on"],
        product=PublicProduct(
            title=content.title,
            description=content.public_description,
            product_type=source["product_type"],
            selling_unit=source["selling_unit"],
        ),
        price=PublicPrice(amount=price),
        costs=_costs(review, content),
        quality_requirements=requirements,
        quality_summary=_quality_summary(review) if policy.include_quality_summary else None,
        market_context=_market_context(review) if policy.include_market_context else None,
        notices=notices,
    )


def payload_dict(payload: PublicPassport) -> dict:
    return payload.model_dump(mode="json", exclude_none=True)


def digest(payload: PublicPassport) -> str:
    return public_digest(payload)
