from datetime import date
from decimal import Decimal, localcontext

import pytest

from fairmade.cost_calendar.domain import month_index, month_start
from fairmade.money_changes import difference


def read(client, headers, source, body=None):
    return client.post(source["path"] + "/cost-calendar", headers=headers, json=body or {})


def test_complete_months_latest_snapshots_and_exact_annual_comparison(
    market_client, market_headers, calendar_source, seed_calendar
):
    first = seed_calendar(date(2025, 1, 15), "2")
    seed_calendar(date(2026, 1, 10), "3")
    latest = seed_calendar(date(2026, 1, 20), "4")
    seed_calendar(date(2024, 10, 31), "99")  # outside the selected window
    seed_calendar(date(2026, 11, 1), "99")  # incomplete month, excluded
    response = read(market_client, market_headers, calendar_source)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["start_date"] == "2024-11-01" and body["end_date"] == "2026-11-01"
    assert len(body["months"]) == 24 and body["recorded_months"] == 2
    assert body["total_snapshots"] == 3
    january = next(row for row in body["months"] if row["month"] == "2026-01")
    assert january["latest_analysis_id"] == latest and january["record_count"] == 2
    assert january["unit_cost"] == "4.000000"
    annual = next(row for row in body["year_over_year"] if row["current_month"] == "2026-01")
    assert annual["previous_analysis_id"] == first
    assert annual["difference"] == {"change": "2.000000", "relative_change": "1.000000"}
    summary = body["calendar_month_summaries"][0]
    assert summary["observed_years"] == [2025, 2026]
    assert summary["minimum_unit_cost"] == "2.000000" and summary["maximum_unit_cost"] == "4.000000"
    assert body["seasonality_status"] == "not_established"
    assert body["calendar_evidence_status"] == "descriptive_comparisons_available"
    assert "PRIVATE_CALENDAR_COST_LABEL" not in response.text
    assert "inputs" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_window_start_is_included_and_current_month_start_is_excluded(
    market_client, market_headers, calendar_source, seed_calendar
):
    identifier = seed_calendar(date(2024, 11, 1), "1")
    seed_calendar(date(2026, 11, 1), "99")
    response = read(market_client, market_headers, calendar_source)
    assert response.status_code == 200
    assert response.json()["total_snapshots"] == 1
    assert response.json()["months"][0]["latest_analysis_id"] == identifier


def test_missing_months_and_recorded_zero_have_distinct_meaning(
    market_client, market_headers, calendar_source, seed_calendar
):
    seed_calendar(date(2025, 1, 15), "0")
    seed_calendar(date(2026, 1, 15), "1")
    response = read(market_client, market_headers, calendar_source)
    assert response.status_code == 200
    body = response.json()
    absent = next(row for row in body["months"] if row["month"] == "2025-02")
    assert absent["status"] == "missing" and absent["unit_cost"] is None
    prior = next(row for row in body["months"] if row["month"] == "2025-01")
    assert prior["status"] == "recorded" and prior["unit_cost"] == "0.000000"
    annual = next(row for row in body["year_over_year"] if row["current_month"] == "2026-01")
    assert annual["difference"]["change"] == "1.000000"
    assert annual["difference"]["relative_change"] is None


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"unit": "pair"}, "basis_changed"),
        ({"kind": "eggs"}, "basis_changed"),
        ({"version": "future-v2"}, "unsupported_snapshot"),
        ({"currency": "EUR"}, "unsupported_snapshot"),
    ],
)
def test_latest_incompatible_or_unsupported_snapshot_is_not_skipped(
    market_client, market_headers, calendar_source, seed_calendar, changes, status
):
    seed_calendar(date(2026, 1, 5), "1")
    identifier = seed_calendar(date(2026, 1, 20), "2", **changes)
    response = read(market_client, market_headers, calendar_source)
    assert response.status_code == 200
    row = next(item for item in response.json()["months"] if item["month"] == "2026-01")
    assert row["status"] == status and row["latest_analysis_id"] == identifier
    assert row["unit_cost"] is None and row["compatible_record_count"] == 1


def test_calendar_scope_auth_roles_ownership_and_other_product_exclusion(
    market_client,
    market_headers,
    buyer_headers,
    market_account,
    market_source,
    calendar_source,
    seed_calendar,
):
    assert (
        market_client.post(calendar_source["path"] + "/cost-calendar", json={}).status_code == 401
    )
    assert read(market_client, buyer_headers, calendar_source).status_code == 403
    other = market_account("other-calendar-owner@example.com")
    assert read(market_client, other, calendar_source).status_code == 404
    foreign_product = market_source()
    seed_calendar(date(2026, 1, 5), "999", product_id=foreign_product["product"]["id"])
    response = read(market_client, market_headers, calendar_source)
    assert response.status_code == 200
    assert response.json()["recorded_months"] == 0
    assert response.json()["calendar_evidence_status"] == "insufficient_history"


@pytest.mark.parametrize(
    "body",
    [
        {"months": True},
        {"months": "24"},
        {"months": 0},
        {"months": 37},
        {"private": "PRIVATE_FAKE_VALUE"},
    ],
)
def test_bounded_redacted_calendar_input(market_client, market_headers, calendar_source, body):
    response = read(market_client, market_headers, calendar_source, body)
    assert response.status_code == 422 and "PRIVATE_FAKE_VALUE" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_large_calendar_refuses_truncated_history(
    market_client, market_headers, calendar_source, seed_calendar
):
    seed_calendar(date(2026, 1, 15), count=1001)
    response = read(market_client, market_headers, calendar_source)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "COST_CALENDAR_TOO_LARGE"
    assert "months" not in response.json()


def test_calendar_rollover_and_shared_delta_precision_are_stable():
    assert month_start(month_index(date(2026, 1, 1)) - 1) == date(2025, 12, 1)
    assert month_start(month_index(date(2024, 3, 1)) - 1) == date(2024, 2, 1)
    with localcontext() as context:
        context.prec = 2
        result = difference(Decimal("3"), Decimal("4"))
        assert result.change == Decimal("1.000000")
        assert result.relative_change == Decimal("0.333333")
