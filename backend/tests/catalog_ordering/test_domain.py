from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fairmade.catalog_ordering.domain import Candidate, rank
from fairmade.catalog_ordering.schemas import OrderingOptions
from fairmade.marketplace.schemas import CatalogCard
from fairmade.passports.schemas import PublicQualitySummary


def candidate(identifier=None, unit_amount="10", status="calculated", quality=None, days=0):
    identifier = identifier or str(uuid4())
    card = CatalogCard.model_validate(
        {
            "id": identifier,
            "published_revision": 1,
            "published_at": datetime(2026, 11, 10, tzinfo=UTC) + timedelta(days=days),
            "payload_hash": "a" * 64,
            "payload": {
                "product": {
                    "title": "Example loaf",
                    "product_type": "sourdough",
                    "selling_unit": "loaf",
                },
                "price": {"currency": "USD", "amount": "10.00"},
                "seller_display_name": "Example bakery",
                "passport_id": str(uuid4()),
                "passport_payload_hash": "b" * 64,
                "notices": [],
                "selling_quantity": {"value": "1000", "unit": "g"},
                "unit_price": {
                    "currency": "USD",
                    "status": status,
                    "amount": unit_amount,
                    "reference_unit": "kg",
                },
            },
            "availability": {"status": "available", "available_units": 10, "selling_unit": "loaf"},
        }
    )
    summary = (
        PublicQualitySummary(
            status=quality,
            evaluation_count=1,
            failed_count=0,
            unknown_or_unevaluated_count=0,
            outdated_count=0,
        )
        if quality
        else None
    )
    return Candidate(card, summary)


def test_decimal_ordering_does_not_use_binary_float():
    high = candidate(unit_amount="1000000000000000000.000002", days=1)
    low = candidate(unit_amount="1000000000000000000.000001")
    ordered = rank(
        [high, low],
        OrderingOptions(mode="unit_price", product_type="sourdough", reference_unit="kg"),
    )
    assert ordered.identifiers == [str(low.card.id), str(high.card.id)]
    assert Decimal(low.card.payload.unit_price.amount) < high.card.payload.unit_price.amount


def test_equal_values_use_recency_then_stable_id_ties():
    first = candidate(identifier=str(UUID(int=1)))
    second = candidate(identifier=str(UUID(int=2)))
    newer = candidate(days=1)
    ordered = rank([first, newer, second], OrderingOptions(mode="price_asc"))
    assert ordered.identifiers == [str(newer.card.id), str(second.card.id), str(first.card.id)]


def test_below_display_precision_is_never_a_zero_price():
    unknown = candidate(unit_amount=None, status="below_display_precision", days=1)
    known = candidate(unit_amount="0.000001")
    ordered = rank(
        [unknown, known],
        OrderingOptions(mode="unit_price", product_type="sourdough", reference_unit="kg"),
    )
    assert ordered.identifiers[0] == str(known.card.id)
    assert ordered.signals[str(unknown.card.id)].reasons == ["UNIT_PRICE_BELOW_DISPLAY_PRECISION"]


def test_no_comparable_value_results_are_explicit():
    concern = candidate(quality="needs_attention")
    ordered = rank(
        [concern], OrderingOptions(mode="value", product_type="sourdough", reference_unit="kg")
    )
    _, metadata = ordered.page(20, 0)
    assert metadata.compared_count == 0 and metadata.not_compared_count == 1
    assert any("No items can be compared" in notice for notice in metadata.notices)
    assert metadata.items[0].comparison_status == "not_compared"
