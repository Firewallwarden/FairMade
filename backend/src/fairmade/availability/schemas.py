"""Buyer-visible available units; internal stock and reservation detail stay private."""

from typing import Annotated, Literal

from pydantic import Field

from fairmade.pricing.schemas import Contract

AvailabilityStatus = Literal["available", "unavailable", "unknown"]


class ListingAvailability(Contract):
    status: AvailabilityStatus
    available_units: Annotated[int, Field(ge=0, le=1_000_000)] | None = None
    selling_unit: str
    basis: Literal["seller_recorded_stock_with_backend_reservations"] = (
        "seller_recorded_stock_with_backend_reservations"
    )
    notice: str = "Based on seller-recorded stock; checkout rechecks availability."
