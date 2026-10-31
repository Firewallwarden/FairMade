"""Explain saved evidence without changing prices, certifying claims, or using an LLM."""

from datetime import date

from fairmade.comparisons.schemas import ComparisonRequest, ObservationSnapshot
from fairmade.comparisons.service import compare
from fairmade.pricing.schemas import PricingResponse
from fairmade.reviews.schemas import ReviewRequest

REVIEW_VERSION = "seller-pricing-review-v1"


def build_review(request: ReviewRequest, evidence: dict, reviewed_on: date) -> dict:
    pricing = PricingResponse.model_validate(evidence["pricing_analysis"]["result"])
    explanations = []
    warnings = ["UNVERIFIED_INPUTS", "SELLER_CONTROLS_FINAL_PRICE", "NO_OBJECTIVE_FAIRNESS_VERDICT"]

    def explain(code: str, message: str):
        explanations.append({"code": code, "message": message})

    explain(
        "PRODUCTION_ECONOMICS",
        f"The selected saved analysis estimates USD {pricing.costs.unit_cost} per production unit "
        f"and a modeled fee-aware break-even price of USD {pricing.break_even_price}. "
        "These costs and fee assumptions are seller-supplied and unverified.",
    )
    explain(
        "SELLER_MARGIN_TARGETS",
        f"The saved range USD {pricing.sustainable_price_range.minimum} to "
        f"{pricing.sustainable_price_range.maximum} reflects seller-selected margins, "
        "not independently established fairness or a recommendation to change price.",
    )
    if any(item.below_break_even for item in pricing.scenarios):
        warnings.append("LOSS_MAKING_SCENARIOS")
        explain(
            "LOSS_MAKING_SCENARIOS",
            "At least one selected saved scenario loses money under its modeled inputs.",
        )
    if evidence["product"] != evidence["pricing_analysis"]["product_snapshot"]:
        warnings.append("PRODUCT_CHANGED_SINCE_PRICING")
        explain(
            "PRODUCT_CHANGED_SINCE_PRICING",
            "Product metadata changed after the selected analysis. "
            "Its economics remain historical.",
        )

    locks = evidence["quality_lock_set"]
    checks = []
    if not locks["rules"]:
        warnings.append("QUALITY_REQUIREMENTS_NOT_CONFIGURED")
    for evaluation in evidence["quality_evaluations"]:
        applies = (
            evaluation["rule_revision"] == locks["revision"]
            and evaluation["rules_snapshot"] == locks["rules"]
        )
        checks.append(
            {
                "evaluation_id": evaluation["id"],
                "candidate_label": evaluation["candidate_label"],
                "saved_status": evaluation["status"],
                "rule_revision": evaluation["rule_revision"],
                "review_rule_revision": locks["revision"],
                "applies_to_review_rules": applies,
                "checks": evaluation["checks"],
            }
        )
        if not applies:
            warnings.append("QUALITY_EVALUATION_OUTDATED")
            explain(
                "QUALITY_EVALUATION_OUTDATED",
                f"Evaluation {evaluation['id']} does not establish compliance "
                "with the rules captured in this review.",
            )
        if evaluation["status"] == "failed":
            warnings.append("MANDATORY_QUALITY_REQUIREMENT_FAILED")
            explain(
                "MANDATORY_QUALITY_REQUIREMENT_FAILED",
                f"Candidate {evaluation['candidate_label']} failed a mandatory requirement "
                "in the saved check. Do not treat it as an acceptable saving.",
            )
        elif evaluation["status"] in ("unknown", "not_evaluated"):
            warnings.append("QUALITY_COMPLIANCE_NOT_ESTABLISHED")
            explain(
                "QUALITY_COMPLIANCE_NOT_ESTABLISHED",
                f"Candidate {evaluation['candidate_label']} has missing "
                "or unevaluated quality information.",
            )
    if not checks:
        quality_status = "not_provided"
        warnings.append("QUALITY_EVIDENCE_MISSING")
        explain(
            "QUALITY_EVIDENCE_MISSING",
            "No quality evaluations were selected; compliance has not been established.",
        )
    elif any(
        item["saved_status"] != "passed" or not item["applies_to_review_rules"] for item in checks
    ):
        quality_status = "needs_attention"
    else:
        quality_status = "claims_match_unverified"
        explain(
            "QUALITY_CLAIMS_UNVERIFIED",
            "Selected claims matched the captured requirements, but the backend "
            "has not verified those claims or certified quality.",
        )
    warnings.append("QUALITY_NOT_VERIFIED")

    market = {"status": "not_provided", "reassessed_comparison": None, "price_assessments": []}
    selected = evidence["comparison_report"]
    if selected is None:
        warnings.append("COMPARISON_EVIDENCE_MISSING")
        explain(
            "COMPARISON_EVIDENCE_MISSING",
            "No comparison report was selected; market context is missing.",
        )
    elif (
        selected["product_snapshot"]["product_type"]
        != evidence["pricing_analysis"]["product_snapshot"]["product_type"]
    ):
        market["status"] = "product_type_mismatch"
        warnings.append("EVIDENCE_PRODUCT_TYPES_DIFFER")
        explain(
            "EVIDENCE_PRODUCT_TYPES_DIFFER",
            "The saved pricing and comparison reports describe different product types. "
            "No numeric price assessment was performed.",
        )
    else:
        original_request = ComparisonRequest.model_validate(selected["request_snapshot"])
        mapping = request.production_unit_quantity
        comparison_request = original_request.model_copy(
            update={"target_quantity": mapping} if mapping else {},
        )
        observations = [
            ObservationSnapshot(id=row["observation_id"], details=row["details"])
            for row in selected["result"]["rows"]
        ]
        refreshed = compare(
            comparison_request,
            observations,
            evidence["pricing_analysis"]["product_snapshot"]["product_type"],
            reviewed_on,
        )
        market["reassessed_comparison"] = refreshed.model_dump(mode="json")
        warnings.extend(refreshed.warnings)
        if selected["as_of_date"] != reviewed_on.isoformat():
            explain(
                "EVIDENCE_FRESHNESS_REASSESSED",
                "Selected quotes were checked again against the review date using "
                "the comparison report's captured freshness cutoff. "
                "The earlier report is unchanged.",
            )
        if mapping is None:
            market["status"] = "basis_missing"
            warnings.append("PRICE_BASIS_NOT_LINKED")
            explain(
                "PRICE_BASIS_NOT_LINKED",
                "Pricing is per production unit; comparison evidence uses its own quantity. "
                "Supply an explicit quantity for one production unit "
                "before comparing their prices.",
            )
        else:
            explain(
                "PRODUCTION_UNIT_MAPPING_UNVERIFIED",
                f"The seller declares that one production unit equals "
                f"{mapping.value} {mapping.unit}. "
                "This mapping is not independently verified.",
            )
            warnings.append("PRODUCTION_UNIT_MAPPING_UNVERIFIED")
            bounds = refreshed.selected_price_range
            if bounds.minimum is None:
                market["status"] = "no_comparable_evidence"
                explain(
                    "NO_COMPARABLE_EVIDENCE",
                    "No selected quote is fresh, same-type, "
                    "and convertible to the declared production unit.",
                )
            else:
                market["status"] = "comparable"
                prices = [
                    ("break_even_price", pricing.break_even_price),
                    ("target_range_minimum", pricing.sustainable_price_range.minimum),
                    ("target_range_maximum", pricing.sustainable_price_range.maximum),
                ] + [("scenario_price", item.price) for item in pricing.scenarios]
                for index, (metric, price) in enumerate(prices):
                    relation = (
                        "below"
                        if price < bounds.minimum
                        else "above"
                        if price > bounds.maximum
                        else "within"
                    )
                    market["price_assessments"].append(
                        {
                            "metric": metric,
                            "price": str(price),
                            "displayed_range_relation": relation,
                            "scenario_index": index - 3 if metric == "scenario_price" else None,
                        }
                    )
                explain(
                    "SELECTED_PRICE_CONTEXT",
                    f"{bounds.included_count} selected quote(s) form a descriptive range "
                    f"USD {bounds.minimum} to {bounds.maximum} on the declared unit basis. "
                    "Relations use these six-decimal displayed bounds, "
                    "not a recommended selling price.",
                )
        if checks:
            warnings.append("QUALITY_EVIDENCE_NOT_LINKED_TO_MARKET_QUOTES")
            explain(
                "QUALITY_EVIDENCE_NOT_LINKED_TO_MARKET_QUOTES",
                "Quality evaluations are separate candidate evidence. "
                "They do not prove that the compared quotes describe equivalent quality.",
            )

    explain(
        "DECISION_BOUNDARY",
        "The seller retains the final pricing decision. This review does not verify "
        "sources, certify quality, establish objective fairness, "
        "or recommend lower-quality savings.",
    )
    return {
        "reviewed_on": reviewed_on.isoformat(),
        "economics": pricing.model_dump(mode="json"),
        "quality": {
            "status": quality_status,
            "captured_rule_revision": locks["revision"],
            "evaluations": checks,
        },
        "market_context": market,
        "explanations": explanations,
        "warnings": list(dict.fromkeys(warnings)),
    }
