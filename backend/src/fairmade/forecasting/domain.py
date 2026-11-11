"""Calendar-day observed rate, exact projection and conservative whole-unit planning."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext

from fairmade.forecasting.records import SaleObservation
from fairmade.forecasting.schemas import (
    DailySales,
    ForecastRequest,
    ForecastResponse,
    History,
    InventoryProjection,
)
from fairmade.stock import StockBalance

MIN_COMPLETE_DAYS = 14
MIN_SALE_DATES = 3
NOTICES = [
    "An observed sandbox sales-rate baseline, not a calibrated forecast or guarantee of demand.",
    "Days without qualifying sales contribute zero; listing exposure and stockouts are unknown.",
    "Uses complete UTC dates after product creation; today's partial sales are excluded.",
    "All refund-request orders are excluded, even denied requests; "
    "this is not net demand accounting.",
    "Matching product/unit labels do not verify identical contents, quality or variants.",
    "No seasonality, trend, promotions, unmet demand, offline sales or lead times are inferred.",
    "Stock is seller-recorded and includes backend holds; raw material needs are not forecast.",
    "Planning numbers change no stock, production, purchase, price, Quality Lock or payment.",
    "Rounded displays are not reused in calculations; additional units use the exact rate/ceiling.",
]


def displayed(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def calculate(
    *,
    product_id: str,
    product_type: str,
    selling_unit: str,
    created_on: date,
    today: date,
    request: ForecastRequest,
    observations: list[SaleObservation],
    stock: StockBalance,
) -> ForecastResponse:
    start = max(today - timedelta(days=request.lookback_days), created_on + timedelta(days=1))
    complete_days = max(0, (today - start).days)
    # A future/inconsistent creation date never creates a reversed display interval.
    start = min(start, today)
    daily = {start + timedelta(days=index): 0 for index in range(complete_days)}
    refund_lines = basis_lines = timing_lines = included = 0
    for row in observations:
        captured_on = row.captured_at.date()
        if (
            captured_on not in daily
            or row.captured_at < row.ordered_at
            or row.ordered_at.date() < created_on
        ):
            timing_lines += 1
        elif row.has_refund_request:
            refund_lines += 1
        elif row.product_type != product_type or row.selling_unit != selling_unit:
            basis_lines += 1
        else:
            daily[captured_on] += row.quantity
            included += 1
    units = sum(daily.values())
    sale_dates = sum(value > 0 for value in daily.values())
    warnings = []
    if complete_days < MIN_COMPLETE_DAYS:
        warnings.append("INSUFFICIENT_COMPLETE_DAYS")
    if sale_dates < MIN_SALE_DATES:
        warnings.append("INSUFFICIENT_SALE_DATES")
    enough = not warnings
    for count, code in [
        (refund_lines, "REFUND_LINES_EXCLUDED"),
        (basis_lines, "HISTORICAL_BASIS_LINES_EXCLUDED"),
        (timing_lines, "INCONSISTENT_TIMING_LINES_EXCLUDED"),
    ]:
        if count:
            warnings.append(code)
    known_stock = stock.revision > 0 and stock.selling_unit == selling_unit and stock.available >= 0
    if not known_stock:
        warnings.append("INVENTORY_UNKNOWN")
    inventory = InventoryProjection(
        status="known" if known_stock else "unknown",
        available_units=stock.available if known_stock else None,
        projected_remaining_units=None,
        additional_whole_units=None,
        days_of_cover=None,
    )
    rate = projected = None
    if enough:
        with localcontext() as context:
            context.prec = 60
            rate = Decimal(units) / complete_days
            projected = Decimal(units) * request.horizon_days / complete_days
            if known_stock:
                required = (units * request.horizon_days + complete_days - 1) // complete_days
                inventory.projected_remaining_units = displayed(
                    Decimal(stock.available) - projected
                )
                inventory.additional_whole_units = max(0, required - stock.available)
                inventory.days_of_cover = displayed(
                    Decimal(stock.available) * complete_days / units
                )
            rate, projected = displayed(rate), displayed(projected)
    return ForecastResponse(
        product_id=product_id,
        product_type=product_type,
        selling_unit=selling_unit,
        as_of_date=today,
        request=request,
        status="baseline_available" if enough else "insufficient_history",
        history=History(
            start_date=start,
            end_date=today,
            complete_days=complete_days,
            sale_dates=sale_dates,
            included_lines=included,
            units=units,
            excluded_refund_lines=refund_lines,
            excluded_basis_lines=basis_lines,
            excluded_timing_lines=timing_lines,
            days=[DailySales(date=day, units=count) for day, count in daily.items()],
        ),
        daily_rate=rate,
        projected_units=projected,
        inventory=inventory,
        warnings=warnings,
        notices=NOTICES,
    )
