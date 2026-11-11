"""Owner/public projections only. No model controls resource selection or database queries."""

from decimal import Decimal, localcontext

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.assistants.history import history_evidence
from fairmade.assistants.schemas import BuyerQuestion, Evidence, SellerQuestion
from fairmade.assistants.supplier_explanations import supplier_details
from fairmade.auth import api_error
from fairmade.baskets.integration import evidence as basket_evidence
from fairmade.bundles.integration import evidence as bundle_evidence
from fairmade.evidence import today
from fairmade.forecasting.integration import TITLE as FORECAST_TITLE
from fairmade.forecasting.service import forecast
from fairmade.marketplace.service import get_public
from fairmade.models import Analysis, QualityLockSet
from fairmade.ownership import require_owned_product
from fairmade.personalization.constants import TITLE as PROFILE_TITLE
from fairmade.personalization.service import buyer_profile_data
from fairmade.pricing.schemas import PricingRequest, PricingResponse
from fairmade.pricing.service import calculate
from fairmade.seller_insights.integration import TITLE as INSIGHT_TITLE
from fairmade.seller_insights.service import report as insight_report


def add(facts: list[Evidence], title: str, data: dict, basis="seller_reported_unverified"):
    facts.append(Evidence(key=f"e{len(facts) + 1}", title=title, basis=basis, data=data))


def seller_evidence(db: Session, account_id: str, body: SellerQuestion) -> list[Evidence]:
    product = require_owned_product(db, account_id, body.product_id)
    facts: list[Evidence] = []
    add(
        facts,
        "Selected private product",
        {
            "product_id": product.id,
            "name": product.name,
            "product_type": product.product_type,
            "selling_unit": product.selling_unit,
        },
    )
    statement = select(Analysis).where(Analysis.product_id == product.id)
    if body.analysis_id:
        statement = statement.where(Analysis.id == str(body.analysis_id))
    analysis = db.scalar(
        statement.order_by(Analysis.created_at.desc(), Analysis.id.desc()).limit(1)
    )
    if body.analysis_id and analysis is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    if analysis is not None:
        if analysis.calculation_version != "production-economics-v1":
            raise api_error(409, "UNSUPPORTED_EVIDENCE_VERSION", "Unsupported analysis version.")
        result = PricingResponse.model_validate(analysis.result)
        add(
            facts,
            "Selected saved production economics",
            {
                "analysis_id": analysis.id,
                "created_at": analysis.created_at.isoformat(),
                "sellable_units": analysis.inputs["sellable_units"],
                "payment_fees": analysis.inputs["payment_fees"],
                "target_margin": analysis.inputs["target_margin"],
                "product_snapshot": {
                    key: analysis.product_snapshot[key]
                    for key in ("name", "product_type", "selling_unit")
                },
                "result": result.model_dump(mode="json"),
            },
            "seller_supplied_unverified",
        )
    else:
        add(facts, "Missing economics", {"status": "No saved production analysis is available."})
    locks = db.get(QualityLockSet, product.id)
    add(
        facts,
        "Current mandatory Quality Locks",
        {
            "revision": locks.revision if locks else 0,
            "rules": locks.rules if locks else [],
            "policy": "Never relax mandatory requirements. Matching claims are not certification.",
        },
    )
    if body.supplier_report_id:
        add(
            facts,
            "Current supplier comparison of selected saved quote evidence",
            supplier_details(db, product.id, body.supplier_report_id, today()),
        )
    history_evidence(db, account_id, body, facts)
    if body.insights is not None:
        add(
            facts,
            INSIGHT_TITLE,
            insight_report(db, account_id, product.id, body.insights, body.analysis_id).model_dump(
                mode="json"
            ),
            "seller_recorded_unverified_and_deterministic_modeled_inputs",
        )
    if body.forecast is not None:
        add(
            facts,
            FORECAST_TITLE,
            forecast(db, account_id, product.id, body.forecast).model_dump(mode="json"),
            "calculated_from_backend_verified_sandbox_sales_and_seller_recorded_stock",
        )
    if body.bundles is not None:
        for fact in bundle_evidence(db, account_id, body.bundles, product_id=product.id):
            fact.key = f"e{len(facts) + 1}"
            facts.append(fact)
    return facts


def scenario_evidence(
    db: Session, body: SellerQuestion, facts: list[Evidence], proposed_prices: list
) -> None:
    economics = next((fact for fact in facts if "analysis_id" in fact.data), None)
    if not proposed_prices or economics is None:
        return
    # Reuse the validated calculator. The language model only extracts proposed inputs.
    analysis = db.get(Analysis, economics.data["analysis_id"])
    if analysis is None:
        raise api_error(409, "ASSISTANT_EVIDENCE_CHANGED", "Evidence changed; ask again.")
    inputs = PricingRequest.model_validate(
        {**analysis.inputs, "proposed_prices": [str(price) for price in proposed_prices]}
    )
    result = calculate(inputs)
    add(
        facts,
        "Deterministic requested price scenarios",
        {
            "analysis_id": analysis.id,
            "selling_unit": analysis.product_snapshot["selling_unit"],
            "currency": result.currency,
            "scenarios": [scenario.model_dump(mode="json") for scenario in result.scenarios],
            "assumptions": result.assumptions,
        },
        "calculated_from_seller_supplied_unverified_inputs",
    )


def buyer_evidence(
    db: Session, body: BuyerQuestion, account_id: str | None = None
) -> list[Evidence]:
    if body.bundles is not None:
        if account_id is None:
            raise api_error(401, "UNAUTHORIZED", "A valid bearer token is required.")
        return bundle_evidence(db, account_id, body.bundles)
    if body.basket is not None:
        if account_id is None:
            raise api_error(401, "UNAUTHORIZED", "A valid bearer token is required.")
        return basket_evidence(db, account_id, body.basket)
    facts: list[Evidence] = []
    listings = []
    for listing_id in body.listing_ids:
        detail = get_public(db, str(listing_id))
        listings.append(detail)
        # The established public allowlist is the ONLY buyer source, including disclosures.
        add(
            facts,
            "Currently approved public listing and Passport",
            detail.model_dump(mode="json", exclude_none=True),
        )
    comparisons = []
    for index, left in enumerate(listings):
        for right in listings[index + 1 :]:
            left_unit = left.payload.unit_price
            right_unit = right.payload.unit_price
            compatible = (
                left.payload.product.product_type == right.payload.product.product_type
                and left_unit is not None
                and right_unit is not None
                and left_unit.status == right_unit.status == "calculated"
                and left_unit.reference_unit == right_unit.reference_unit
                and left_unit.currency == right_unit.currency
            )
            difference = None
            if compatible:
                with localcontext() as context:
                    context.prec = 60
                    difference = str(Decimal(left_unit.amount) - Decimal(right_unit.amount))
            comparisons.append(
                {
                    "left_listing_id": str(left.id),
                    "right_listing_id": str(right.id),
                    "compatible_price_basis": compatible,
                    "left_minus_right_unit_price": difference,
                    "reference_unit": left_unit.reference_unit if compatible else None,
                    "interpretation": (
                        "Difference between rounded unit-price displays; not a value ranking."
                        if compatible
                        else "Price comparison unavailable: missing or incompatible basis."
                    ),
                }
            )
    if comparisons:
        add(
            facts,
            "Deterministic public unit-price comparisons",
            {"currency": "USD", "pairs": comparisons},
            "calculated_from_approved_public_inputs",
        )
    add(
        facts,
        "Comparison limitations",
        {
            "policy": "Compare prices only when product type, currency and reference unit match. "
            "Matching dimensions do not establish equal quality, grade or overall value. "
            "Missing disclosures are unknown, not zero. Stock is not reserved by this answer."
        },
        "application_policy",
    )
    if account_id is not None:
        personalization = buyer_profile_data(db, account_id, listings)
        if personalization is not None:
            add(
                facts,
                PROFILE_TITLE,
                personalization,
                "buyer_confirmed_preferences_and_private_activity",
            )
    return facts
