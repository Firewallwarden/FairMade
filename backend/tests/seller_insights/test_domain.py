from datetime import date
from decimal import Decimal
from uuid import uuid4

from fairmade.seller_insights import domain
from fairmade.seller_insights.records import CostObservation


def test_changes_keep_unknowns_and_zero_baseline_distinct():
    assert domain.difference(None, Decimal(5)).change is None
    change = domain.difference(Decimal(0), Decimal(5))
    assert change.change == Decimal(5) and change.relative_change is None
    assert domain.difference(Decimal(3), Decimal(4)).relative_change == Decimal("0.333333")


def test_cost_history_does_not_skip_latest_incompatible_snapshot():
    records = [
        CostObservation(str(uuid4()), date(2026, 1, 1), "sourdough", "loaf", Decimal(5)),
        CostObservation(str(uuid4()), date(2026, 2, 1), "sourdough", "loaf", Decimal(6)),
        CostObservation(str(uuid4()), date(2026, 2, 2), "sourdough", "pair", Decimal(12)),
    ]
    result = domain.cost_comparison(records, date(2026, 2, 1), "sourdough", "loaf")
    assert result.status == "incompatible_basis"
    assert result.difference.change is None and result.current_unit_cost is None


def test_material_waste_keeps_identifiers_and_units_separate():
    left, right = str(uuid4()), str(uuid4())
    result = domain.material_waste(
        [(left, "A", "g", 2000000, 1000000), (right, "B", "ml", 4000000, 3000000)]
    )
    assert len(result) == 2
    assert {row.unit for row in result} == {"g", "ml"}
    assert all(row.quantity == Decimal(1) for row in result)
