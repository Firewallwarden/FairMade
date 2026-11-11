"""Plain-text, retry-safe messages with minimal participant-facing identities."""

import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from fairmade.pricing.schemas import Contract
from fairmade.schemas import UTCResponse

ParticipantRole = Literal["buyer", "seller"]


class SendMessage(Contract):
    request_id: UUID
    text: Annotated[str, Field(strict=True, min_length=1, max_length=2000)]

    @field_validator("text", mode="before")
    @classmethod
    def normalized_newlines(cls, value):
        if isinstance(value, str) and len(value) > 4000:
            raise ValueError("Raw message text must be at most 4000 characters")
        return value.replace("\r\n", "\n").replace("\r", "\n") if isinstance(value, str) else value

    @field_validator("text")
    @classmethod
    def plain_text(cls, value: str) -> str:
        if any(unicodedata.category(char) in {"Cc", "Cs"} and char not in "\n\t" for char in value):
            raise ValueError("Use valid plain text without unsupported control characters")
        return value


class MessageResponse(UTCResponse):
    id: UUID
    sequence: int
    sender: ParticipantRole
    is_mine: bool
    text: str
    created_at: datetime


class MessagePage(Contract):
    order_id: UUID
    my_role: ParticipantRole
    items: list[MessageResponse]
    after_sequence: int
    next_after_sequence: int
    limit: int
    has_more: bool
    notices: list[str] = [
        "Order messages are private to the order's buyer and currently authorized seller.",
        "Messages are plain text and perform no payment, refund, fulfillment or assistant action.",
        "History is retained with the order; there is no automatic message expiry or deletion.",
    ]
