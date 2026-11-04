"""Capture-cohort estimates; sales receipts and modeled profit stay distinct."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

from fairmade.sales.records import SaleRecord
from fairmade.sales.schemas import SalesOrderResponse, SalesSummary

WARNINGS = [
    "SANDBOX_SHARED_MERCHANT_NOT_SELLER_PAYOUTS",
    "ONLY_COMPLETED_VERIFIED_CAPTURES_INCLUDED",
    "CAPTURE_COHORT_WITH_REFUNDS_AS_OF_REPORT_NOT_PERIOD_CASH_FLOW",
    "SELLER_PRODUCTION_COSTS_UNVERIFIED_AND_MAY_BE_INCOMPLETE",
    "ORIGINAL_CAPTURE_FEES_RETAINED_REFUND_FEE_CHANGES_NOT_MODELED",
    "REFUNDS_DO_NOT_REVERSE_MODELED_PRODUCTION_COSTS_OR_RESTOCK",
    "TAX_SHIPPING_FINANCING_AND_OTHER_UNRECORDED_COSTS_NOT_MODELED",
]


def usd(minor: int) -> Decimal:
    return Decimal(minor).scaleb(-2).quantize(Decimal("0.01"))


def _margin(profit: Decimal | None, sales_less_refunds: Decimal) -> Decimal | None:
    if profit is None or sales_less_refunds <= 0:
        return None
    return (profit / sales_less_refunds).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def order_result(record: SaleRecord) -> SalesOrderResponse:
    with localcontext() as context:
        context.prec = 60
        return _order_result(record)


def _order_result(record: SaleRecord) -> SalesOrderResponse:
    reasons = []
    fee_minor = record.fee_minor
    fee_basis = "provider_fee"
    if fee_minor is None:
        if record.net_minor is not None:
            fee_minor = record.gross_minor - record.net_minor
            fee_basis = "derived_from_provider_net"
        else:
            fee_basis = "unavailable"
            reasons.append("PROCESSING_FEE_UNAVAILABLE")
    cost = None
    if record.cost_status == "available" and record.cost_total is not None:
        cost = Decimal(record.cost_total)
    else:
        reasons.append(
            "COST_SNAPSHOT_MISSING" if record.cost_status is None else "COST_BASIS_UNAVAILABLE"
        )
    if record.refund_state in ("refund_pending", "needs_review"):
        reasons.append("REFUND_UNRESOLVED")
    refund_minor = (
        record.refund_minor
        if record.refund_state == "refunded" and record.refund_verified_at is not None
        else 0
    )
    gross = usd(record.gross_minor)
    refund = usd(refund_minor)
    fee = usd(fee_minor) if fee_minor is not None else None
    after_fee = gross - refund - fee if fee is not None else None
    profit = after_fee - cost if not reasons else None
    warnings = list(WARNINGS)
    if record.refund_state == "requested":
        warnings.append("OPEN_REFUND_REQUEST_NOT_DEDUCTED")
    if record.cost_details:
        for item in record.cost_details["items"]:
            source = item.get("source")
            if source:
                warnings.extend(source.get("warnings", []))
    return SalesOrderResponse(
        order_id=record.order_id,
        created_at=record.created_at,
        captured_at=record.captured_at,
        gross_sales=gross,
        completed_refunds=refund,
        processing_fee=fee,
        fee_basis=fee_basis,
        after_refunds_and_fee=after_fee,
        estimated_production_cost=cost,
        estimated_profit=profit,
        estimated_margin=_margin(profit, gross - refund),
        profit_unavailable_reasons=reasons,
        cost_snapshot=record.cost_details,
        warnings=list(dict.fromkeys(warnings)),
    )


def summarize(
    records: list[SaleRecord],
    start_date: date,
    end_date: date,
    generated_at: datetime,
) -> SalesSummary:
    with localcontext() as context:
        context.prec = 60
        rows = [_order_result(record) for record in records]
        zero = Decimal("0.00")
        gross = sum((row.gross_sales for row in rows), zero)
        refunds = sum((row.completed_refunds for row in rows), zero)
        covered = [row for row in rows if row.estimated_profit is not None]
        covered_profit = sum((row.estimated_profit for row in covered), zero)
        profit = covered_profit if len(covered) == len(rows) else None
        warnings = list(WARNINGS)
        if len(covered) != len(rows):
            warnings.append("PROFIT_COVERAGE_INCOMPLETE")
        return SalesSummary(
            start_date=start_date,
            end_date=end_date,
            generated_at=generated_at,
            sales_count=len(rows),
            gross_sales=gross,
            completed_refunds=refunds,
            sales_less_refunds=gross - refunds,
            known_processing_fees=sum(
                (row.processing_fee for row in rows if row.processing_fee is not None),
                zero,
            ),
            known_estimated_production_costs=sum(
                (
                    row.estimated_production_cost
                    for row in rows
                    if row.estimated_production_cost is not None
                ),
                zero,
            ),
            missing_fee_count=sum(row.processing_fee is None for row in rows),
            missing_cost_count=sum(row.estimated_production_cost is None for row in rows),
            unresolved_refund_count=sum(
                "REFUND_UNRESOLVED" in row.profit_unavailable_reasons for row in rows
            ),
            covered_sales_count=len(covered),
            covered_estimated_profit=covered_profit,
            estimated_profit=profit,
            estimated_margin=_margin(profit, gross - refunds),
            warnings=warnings,
        )
