"""Minimal payment DTOs; raw PayPal responses and payer data never leave the adapter."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fairmade.passports.schemas import PublicPrice
from fairmade.pricing.schemas import Contract


class EmptyRequest(Contract):
    pass


class PublicConfig(Contract):
    enabled: bool
    environment: Literal["sandbox"] = "sandbox"
    merchant_mode: Literal["shared"] = "shared"
    currency: Literal["USD"] = "USD"
    client_id: str | None = None


class CheckoutResponse(Contract):
    order_id: UUID
    environment: Literal["sandbox"] = "sandbox"
    merchant_mode: Literal["shared"] = "shared"
    state: Literal["creating", "ready", "capture_pending", "completed", "failed", "needs_review"]
    provider_order_id: str | None = None
    provider_status: str | None = None
    capture_id: str | None = None
    amount: PublicPrice
    sandbox_fee: PublicPrice | None = None
    sandbox_net: PublicPrice | None = None
    verified_at: datetime | None = None
