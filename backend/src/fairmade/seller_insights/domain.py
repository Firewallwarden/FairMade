"""Deterministic comparisons and cautious review opportunities, never invented savings."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from fairmade.seller_insights.records import CostObservation
from fairmade.seller_insights.schemas import (
    AmountChange,
    CostComparison,
    InsightAlert,
    InsightReport,
    MaterialWaste,
    ProductionOutput,
)


def displayed(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def difference(previous: Decimal | None, current: Decimal | None) -> AmountChange:
    if previous is None or current is None:
        return AmountChange(change=None, relative_change=None)
    with localcontext() as context:
        context.prec = 50
        delta = current - previous
        return AmountChange(
            change=displayed(delta),
            relative_change=displayed(delta / previous) if previous else None,
        )


def cost_comparison(
    records: list[CostObservation], split, product_type: str, unit: str
) -> CostComparison:
    prior = [row for row in records if row.created_on < split]
    current = [row for row in records if row.created_on >= split]
    empty = difference(None, None)
    if not prior or not current:
        return CostComparison(status="missing_period_evidence", difference=empty)
    left, right = prior[-1], current[-1]
    compatible = all(
        row.product_type == product_type and row.selling_unit == unit and row.unit_cost is not None
        for row in (left, right)
    )
    return CostComparison(
        status="available" if compatible else "incompatible_basis",
        previous_analysis_id=left.identifier,
        current_analysis_id=right.identifier,
        previous_saved_on=left.created_on,
        current_saved_on=right.created_on,
        previous_unit_cost=left.unit_cost if compatible else None,
        current_unit_cost=right.unit_cost if compatible else None,
        difference=difference(left.unit_cost, right.unit_cost) if compatible else empty,
    )


def production_output(rows: list, unit: str, product_type: str) -> ProductionOutput:
    compatible = [row for row in rows if row[0] == unit and row[3] == product_type]
    total = sum(row[1] for row in compatible)
    sellable = sum(row[2] for row in compatible)
    with localcontext() as context:
        context.prec = 50
        return ProductionOutput(
            included_records=len(compatible),
            excluded_basis_records=len(rows) - len(compatible),
            total_units=total,
            sellable_units=sellable,
            non_sellable_units=total - sellable,
            sellable_fraction=displayed(Decimal(sellable) / total) if total else None,
        )


def material_waste(rows: list) -> list[MaterialWaste]:
    groups = {}
    with localcontext() as context:
        context.prec = 50
        for identifier, label, unit, before, after in rows:
            key = identifier, unit
            if key not in groups:
                groups[key] = MaterialWaste(
                    material_id=identifier,
                    label=label,
                    unit=unit,
                    quantity=Decimal(0),
                    movement_count=0,
                )
            groups[key].quantity += Decimal(before - after).scaleb(-6)
            groups[key].movement_count += 1
    return sorted(groups.values(), key=lambda item: (str(item.material_id), item.unit))


def alerts(report: InsightReport) -> list[InsightAlert]:
    result = []

    def add(code, severity, scope, source, message, review):
        result.append(
            InsightAlert(
                code=code,
                severity=severity,
                scope=scope,
                source=source,
                message=message,
                suggested_review=review,
            )
        )

    price = report.pricing
    if price.status == "assessed":
        if price.below_break_even:
            add(
                "UNSUSTAINABLE_PRICE",
                "warning",
                "product",
                "pricing",
                "The approved selling price is below modeled fee-aware break-even.",
                "Review costs, fee assumptions and seller margin targets; preserve Quality Locks.",
            )
        elif price.below_target_margin:
            add(
                "LOW_MARGIN",
                "warning",
                "product",
                "pricing",
                "The approved selling price is below the seller's minimum modeled margin target.",
                "Review cost drivers and target scenarios without automatically changing price.",
            )
    if report.costs.difference.change is not None and report.costs.difference.change > 0:
        add(
            "SAVED_UNIT_COST_INCREASE",
            "opportunity",
            "product",
            "cost_history",
            "The latest compatible unit-cost snapshot increased between the closed periods.",
            "Check yield, allocations and costs; "
            "this difference does not prove inflation or a cause.",
        )
    if report.receipts.difference.change is not None and report.receipts.difference.change > 0:
        add(
            "REVIEWED_EXPENSE_TOTAL_INCREASE",
            "opportunity",
            "seller",
            "receipts",
            "Seller-wide approved receipt totals increased between equal-duration periods.",
            "Review category coverage and purchase timing; "
            "do not deduct these totals from profit again.",
        )
    if report.production.non_sellable_units:
        add(
            "NON_SELLABLE_OUTPUT",
            "opportunity",
            "product",
            "production",
            "Completed reports include output that was not sellable.",
            "Review recorded causes and handling; non-sellable output is not automatically waste.",
        )
    if report.materials:
        add(
            "RECORDED_MATERIAL_WASTE",
            "opportunity",
            "seller",
            "materials",
            "The material ledger records waste in this period.",
            "Review storage, handling and portioning as possibilities; "
            "do not infer causes or relax quality.",
        )
    return result
