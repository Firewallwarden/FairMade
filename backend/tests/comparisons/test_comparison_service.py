"""Exact quantity conversions without claims about fairness or equivalent quality."""

from datetime import date, timedelta
from decimal import Decimal, localcontext
from uuid import uuid4

import pytest

from fairmade.comparisons.schemas import ComparisonRequest, ObservationSnapshot
from fairmade.comparisons.service import compare

AS_OF = date(2026, 1, 31)


def report(data, target_value="100", target_unit="g", max_age=30, product_type="sourdough"):
    observation = ObservationSnapshot(id=uuid4(), details=data)
    request = ComparisonRequest.model_validate(
        {
            "observation_ids": [str(observation.id)],
            "target_quantity": {"value": target_value, "unit": target_unit},
            "max_age_days": max_age,
        }
    )
    return compare(request, [observation], product_type, AS_OF)


@pytest.mark.parametrize(
    "product_type,price,quantity,unit,target_value,target_unit,expected",
    [
        ("sourdough", "8", "500", "g", "100", "g", "1.600000"),
        ("sourdough", "8", "0.5", "kg", "100", "g", "1.600000"),
        ("sourdough", "8", "500", "g", "1", "kg", "16.000000"),
        ("sourdough", "16", "2", "loaf", "1", "loaf", "8.000000"),
        ("eggs", "6", "1", "dozen", "1", "egg", "0.500000"),
        ("eggs", "6", "12", "egg", "1", "dozen", "6.000000"),
        ("eggs", "6", "0.5", "dozen", "1", "egg", "1.000000"),
        ("eggs", "0", "1", "dozen", "1", "egg", "0.000000"),
        ("other", "1", "3", "item", "1", "item", "0.333333"),
        ("other", "0.000001", "2", "g", "1", "g", "0.000001"),
    ],
)
def test_supported_normalizations(
    observation_body,
    product_type,
    price,
    quantity,
    unit,
    target_value,
    target_unit,
    expected,
):
    observation_body.update(
        product_type=product_type, price=price, quantity={"value": quantity, "unit": unit}
    )
    checked = report(observation_body, target_value, target_unit, product_type=product_type)
    assert checked.rows[0].normalized_price == Decimal(expected)
    assert checked.rows[0].included_in_range is True
    assert (
        checked.selected_price_range.minimum
        == checked.selected_price_range.maximum
        == Decimal(expected)
    )
    assert checked.rows[0].details.quality_notes == observation_body["quality_notes"]


@pytest.mark.parametrize(
    "age,max_age,included",
    [
        (0, 0, True),
        (1, 0, False),
        (30, 30, True),
        (31, 30, False),
        (365, 365, True),
    ],
)
def test_freshness_is_explicit_and_inclusive(observation_body, age, max_age, included):
    observation_body["observed_on"] = (AS_OF - timedelta(days=age)).isoformat()
    checked = report(observation_body, max_age=max_age)
    row = checked.rows[0]
    assert row.age_days == age
    assert row.stale is (not included)
    assert row.included_in_range is included
    assert row.normalized_price == Decimal("1.600000")
    assert checked.selected_price_range.included_count == int(included)
    assert checked.selected_price_range.minimum == (Decimal("1.600000") if included else None)
    if not included:
        assert "STALE_OBSERVATION" in row.exclusion_reasons
        assert "NO_FRESH_QUANTITY_COMPARABLE_OBSERVATIONS" in checked.warnings


def test_incompatible_units_do_not_invent_loaf_weight(observation_body):
    observation_body["quantity"] = {"value": "1", "unit": "loaf"}
    row = report(observation_body).rows[0]
    assert row.normalized_price is None
    assert row.exclusion_reasons == ["INCOMPATIBLE_UNITS"]
    assert row.included_in_range is False


def test_egg_and_item_counts_are_not_implicitly_equivalent(observation_body):
    observation_body.update(product_type="eggs", quantity={"value": "12", "unit": "egg"})
    row = report(observation_body, "12", "item", product_type="eggs").rows[0]
    assert row.normalized_price is None and row.exclusion_reasons == ["INCOMPATIBLE_UNITS"]


def test_different_product_type_is_excluded_even_for_mass(observation_body):
    observation_body["product_type"] = "eggs"
    row = report(observation_body).rows[0]
    assert row.normalized_price is None
    assert row.exclusion_reasons == ["PRODUCT_TYPE_MISMATCH"]


def test_future_observation_is_defensively_excluded(observation_body):
    observation_body["observed_on"] = (AS_OF + timedelta(days=1)).isoformat()
    checked = report(observation_body)
    assert checked.rows[0].exclusion_reasons == ["FUTURE_OBSERVATION"]
    assert checked.selected_price_range.included_count == 0


def test_all_exclusion_reasons_are_preserved(observation_body):
    observation_body.update(
        product_type="eggs",
        quantity={"value": "1", "unit": "dozen"},
        observed_on=(AS_OF - timedelta(days=31)).isoformat(),
    )
    row = report(observation_body).rows[0]
    assert row.exclusion_reasons == [
        "STALE_OBSERVATION",
        "PRODUCT_TYPE_MISMATCH",
        "INCOMPATIBLE_UNITS",
    ]


def test_range_only_uses_fresh_compatible_selected_observations(observation_body):
    snapshots = []
    for price, age in [("10", 0), ("4", 30), ("100", 31)]:
        data = {
            **observation_body,
            "price": price,
            "observed_on": (AS_OF - timedelta(days=age)).isoformat(),
        }
        snapshots.append(ObservationSnapshot(id=uuid4(), details=data))
    request = ComparisonRequest.model_validate(
        {
            "observation_ids": [str(item.id) for item in snapshots],
            "target_quantity": {"value": "100", "unit": "g"},
        }
    )
    checked = compare(request, snapshots, "sourdough", AS_OF)
    assert checked.selected_price_range.model_dump() == {
        "included_count": 2,
        "excluded_count": 1,
        "minimum": Decimal("0.800000"),
        "maximum": Decimal("2.000000"),
    }
    assert "QUALITY_NOT_EVALUATED" in checked.warnings
    assert "LOCATION_NOT_VERIFIED" in checked.warnings
    assert "TAX_SHIPPING_DISCOUNTS_NOT_NORMALIZED" in checked.warnings


def test_maximum_scale_and_context_isolation(observation_body):
    observation_body.update(price="1000000000", quantity={"value": "0.000001", "unit": "g"})
    with localcontext() as context:
        context.prec = 2
        row = report(observation_body, "1000000000", "g").rows[0]
    assert row.normalized_price == Decimal("1000000000000000000000000.000000")
