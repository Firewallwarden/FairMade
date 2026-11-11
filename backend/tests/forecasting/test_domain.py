from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from fairmade.forecasting.domain import calculate
from fairmade.forecasting.records import SaleObservation
from fairmade.forecasting.schemas import ForecastRequest
from fairmade.stock import StockBalance

TODAY = date(2026, 11, 10)


def sale(days_ago=2, quantity=3, **changes):
    captured = datetime.combine(TODAY - timedelta(days=days_ago), time(12))
    return SaleObservation(
        **{
            "captured_at": captured,
            "ordered_at": captured - timedelta(minutes=1),
            "quantity": quantity,
            "product_type": "sourdough",
            "selling_unit": "loaf",
            "has_refund_request": False,
            **changes,
        }
    )


def result(observations=None, **changes):
    return calculate(
        **{
            "product_id": str(uuid4()),
            "product_type": "sourdough",
            "selling_unit": "loaf",
            "created_on": TODAY - timedelta(days=60),
            "today": TODAY,
            "request": ForecastRequest(),
            "observations": observations
            if observations is not None
            else [sale(day) for day in (2, 4, 7)],
            "stock": StockBalance(1, "loaf", 1, 0),
            **changes,
        }
    )


def test_complete_calendar_baseline_exact_shortfall_and_rounding():
    response = result()
    assert response.status == "baseline_available"
    assert response.history.units == 9 and response.history.complete_days == 28
    assert len(response.history.days) == 28 and response.history.sale_dates == 3
    assert response.daily_rate == Decimal("0.321429")
    assert response.projected_units == Decimal("2.250000")
    assert response.inventory.projected_remaining_units == Decimal("-1.250000")
    assert response.inventory.additional_whole_units == 2
    assert response.inventory.days_of_cover == Decimal("3.111111")
    assert sum(day.units == 0 for day in response.history.days) == 25


def test_fractional_baseline_uses_whole_units_for_planning():
    response = result(
        [sale(day, quantity=1) for day in (2, 4, 7)], stock=StockBalance(1, "loaf", 0, 0)
    )
    assert response.projected_units == Decimal("0.750000")
    assert response.inventory.additional_whole_units == 1
    assert response.inventory.days_of_cover == 0


@pytest.mark.parametrize("rows", [[], [sale(2)], [sale(2), sale(4)], [sale(2, quantity=9999)]])
def test_sparse_history_is_unknown_not_zero_or_artificial_confidence(rows):
    response = result(rows)
    assert response.status == "insufficient_history"
    assert response.projected_units is None and response.daily_rate is None
    assert response.inventory.additional_whole_units is None
    assert "INSUFFICIENT_SALE_DATES" in response.warnings


@pytest.mark.parametrize("age,complete_days", [(0, 0), (1, 0), (8, 7), (14, 13), (15, 14), (-1, 0)])
def test_product_creation_partial_date_is_not_full_exposure(age, complete_days):
    response = result(created_on=TODAY - timedelta(days=age))
    assert response.history.complete_days == complete_days
    assert response.history.start_date <= response.history.end_date
    if complete_days < 14:
        assert response.status == "insufficient_history"
        assert "INSUFFICIENT_COMPLETE_DAYS" in response.warnings


@pytest.mark.parametrize(
    "stock",
    [StockBalance(0, None, 0, 0), StockBalance(1, "item", 10, 0), StockBalance(1, "loaf", 1, 2)],
)
def test_unknown_or_inconsistent_stock_never_becomes_zero_stock_advice(stock):
    response = result(stock=stock)
    assert response.status == "baseline_available"
    assert response.inventory.status == "unknown"
    assert response.inventory.available_units is None
    assert response.inventory.additional_whole_units is None
    assert response.inventory.days_of_cover is None


def test_refunds_wrong_units_types_and_invalid_times_are_excluded():
    rows = [sale(day, quantity=1) for day in (2, 4, 7)] + [
        sale(1, quantity=100, has_refund_request=True),
        sale(1, quantity=100, selling_unit="dozen"),
        sale(1, quantity=100, product_type="eggs"),
        sale(1, quantity=100, selling_unit=None),
        sale(0, quantity=100),
        sale(-1, quantity=100),
        sale(29, quantity=100),
        sale(1, ordered_at=datetime.combine(TODAY, time(1))),
    ]
    response = result(rows)
    assert response.history.units == 3
    assert response.history.excluded_refund_lines == 1
    assert response.history.excluded_basis_lines == 3
    assert response.history.excluded_timing_lines == 4
    assert response.status == "baseline_available"


def test_lookback_boundary_inclusive_end_exclusive():
    response = result([sale(day, quantity=1) for day in (28, 27, 26, 29, 0, -1)])
    assert response.history.units == 3
    assert response.history.start_date == TODAY - timedelta(days=28)
    assert response.history.end_date == TODAY


def test_holds_reduce_available_stock_and_ceiling_does_not_order_extra():
    response = result(stock=StockBalance(2, "loaf", 10, 9))
    assert response.inventory.available_units == 1
    assert response.inventory.additional_whole_units == 2
    ample = result(stock=StockBalance(2, "loaf", 10, 0))
    assert ample.inventory.additional_whole_units == 0
