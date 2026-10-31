"""Explicit stock basis, quantities and optimistic revisions."""

from typing import Annotated
from uuid import UUID

from pydantic import Field

from fairmade.pricing.schemas import Contract, Label

StockCount = Annotated[int, Field(strict=True, ge=0, le=1_000_000)]


class InventoryReplacement(Contract):
    expected_revision: Annotated[int, Field(strict=True, ge=0, le=2_147_483_646)]
    selling_unit: Label
    on_hand: StockCount


class InventoryResponse(Contract):
    product_id: UUID
    revision: int
    configured: bool
    selling_unit: str | None
    on_hand: int
    reserved: int
    available: int
