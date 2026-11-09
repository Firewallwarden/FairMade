"""Pickup progress is independent of verified payment and public seller locations."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.pricing.schemas import Contract
from fairmade.schemas import UTCResponse

PickupState = Literal["preparing", "ready_for_pickup", "collected"]
Instructions = Annotated[str, Field(min_length=1, max_length=2000)]


class PickupUpdate(Contract):
    expected_revision: Annotated[int, Field(strict=True, ge=0, le=2_147_483_646)]
    state: PickupState
    pickup_instructions: Instructions | None = None

    @model_validator(mode="after")
    def ready_requires_instructions(self) -> Self:
        if self.state != "preparing" and self.pickup_instructions is None:
            raise ValueError("Ready and collected states require pickup instructions")
        return self


class PickupEvent(UTCResponse):
    revision: int
    state: PickupState
    pickup_instructions: str | None
    created_at: datetime


class PickupResponse(Contract):
    order_id: UUID
    mode: Literal["local_pickup"] = "local_pickup"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    revision: int
    state: Literal["not_started", "preparing", "ready_for_pickup", "collected"]
    pickup_instructions: str | None
    latest_event: PickupEvent | None
    updates_allowed: bool
    notices: list[str]
