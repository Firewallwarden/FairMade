from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from fairmade.assistants.schemas import (
    AssistantResponse,
    BuyerQuestion,
    BuyerSelection,
    HistoryPeriod,
    Question,
    SellerQuestion,
)
from fairmade.pricing.schemas import Contract
from fairmade.schemas import UTCResponse

ConversationRevision = Annotated[int, Field(strict=True, ge=0, le=40)]


class SellerScope(Contract):
    role: Literal["seller"]
    product_id: UUID
    analysis_id: UUID | None = None
    supplier_report_id: UUID | None = None
    history_period: HistoryPeriod | None = None


class BuyerScope(BuyerSelection):
    role: Literal["buyer"]


Scope = Annotated[SellerScope | BuyerScope, Field(discriminator="role")]


class CreateConversation(Contract):
    request_id: UUID
    scope: Scope


class CreateTurn(Contract):
    request_id: UUID
    expected_revision: ConversationRevision
    question: Question


class ConversationResponse(UTCResponse):
    id: UUID
    role: Literal["buyer", "seller"]
    scope: Scope
    revision: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def utc_expiry(cls, value):
        return cls.utc_timestamp(value)


class ConversationPage(Contract):
    items: list[ConversationResponse]
    limit: int
    offset: int


class TurnResponse(UTCResponse):
    id: UUID
    conversation_id: UUID
    request_id: UUID
    revision: int
    question: str
    answer: AssistantResponse | None
    answer_status: Literal["available", "evidence_changed"]
    context_turns: int
    created_at: datetime


class TurnPage(Contract):
    items: list[TurnResponse]
    limit: int
    offset: int


def question_for(scope: dict, question: str) -> SellerQuestion | BuyerQuestion:
    values = {key: value for key, value in scope.items() if key != "role"}
    schema = SellerQuestion if scope["role"] == "seller" else BuyerQuestion
    return schema.model_validate({**values, "question": question})
