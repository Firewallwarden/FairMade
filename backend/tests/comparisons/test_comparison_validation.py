"""Price evidence cannot claim verification or ambiguous quantities."""

from datetime import date, timedelta
from decimal import localcontext
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fairmade.comparisons.schemas import ComparisonRequest, ObservationCreate, Quantity


@pytest.mark.parametrize(
    "field,value",
    [
        ("price", -1),
        ("price", "-1"),
        ("price", 1),
        ("price", True),
        ("price", "NaN"),
        ("price", "Infinity"),
        ("price", "1000000001"),
        ("price", "0.0000001"),
        ("label", ""),
        ("label", " "),
        ("label", "x" * 201),
        ("location", " "),
        ("currency", "EUR"),
        ("product_type", "supplier_input"),
        ("quality_notes", "x" * 2001),
        ("price_notes", "x" * 2001),
        ("basis", "verified"),
        ("seller_id", str(uuid4())),
        ("observed_on", "invalid"),
        ("observed_on", (date(2026, 1, 31) + timedelta(days=1)).isoformat()),
    ],
)
def test_invalid_observation_fields(observation_body, field, value):
    observation_body[field] = value
    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(observation_body)


@pytest.mark.parametrize(
    "field", ["source", "location", "observed_on", "quantity", "price", "currency"]
)
def test_provenance_and_price_inputs_are_required(observation_body, field):
    del observation_body[field]
    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(observation_body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", " "),
        ("reference", " "),
        ("kind", "verified"),
        ("verified", True),
    ],
)
def test_source_fields_cannot_assert_verification(observation_body, field, value):
    observation_body["source"][field] = value
    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(observation_body)


@pytest.mark.parametrize(
    "quantity",
    [
        {"value": "0", "unit": "g"},
        {"value": "-1", "unit": "g"},
        {"value": "NaN", "unit": "g"},
        {"value": 1, "unit": "g"},
        {"value": "1", "unit": "lb"},
        {"value": "0.5", "unit": "egg"},
        {"value": "0.1", "unit": "dozen"},
        {"value": "0.5", "unit": "loaf"},
        {"value": "0.1", "unit": "item"},
        {"value": "0.0000001", "unit": "g"},
        {"value": "1000000001", "unit": "kg"},
    ],
)
def test_quantity_validation(quantity):
    with pytest.raises(ValidationError):
        Quantity.model_validate(quantity)


def test_half_dozen_is_valid_but_fractional_egg_is_not_under_small_context():
    with localcontext() as context:
        context.prec = 2
        assert Quantity.model_validate({"value": "0.5", "unit": "dozen"}).value
        with pytest.raises(ValidationError):
            Quantity.model_validate({"value": "100.000001", "unit": "egg"})


@pytest.mark.parametrize("unit", ["egg", "dozen"])
def test_named_units_match_product_type(observation_body, unit):
    observation_body["quantity"] = {"value": "1", "unit": unit}
    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(observation_body)


@pytest.mark.parametrize("age", [-1, 366, True, 1.5, "30"])
def test_freshness_cutoff_is_bounded_integer(age):
    with pytest.raises(ValidationError):
        ComparisonRequest.model_validate(
            {
                "observation_ids": [str(uuid4())],
                "target_quantity": {"value": "100", "unit": "g"},
                "max_age_days": age,
            }
        )


def test_observation_selection_is_bounded_unique_and_explicit():
    selected = str(uuid4())
    for ids in ([], [selected, selected], [str(uuid4()) for _index in range(101)], ["invalid"]):
        with pytest.raises(ValidationError):
            ComparisonRequest.model_validate(
                {
                    "observation_ids": ids,
                    "target_quantity": {"value": "100", "unit": "g"},
                }
            )
