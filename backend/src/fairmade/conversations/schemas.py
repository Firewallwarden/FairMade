from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictBool, field_validator, model_validator

from fairmade.assistants.schemas import (
    AssistantResponse,
    BuyerQuestion,
    BuyerSelection,
    HistoryPeriod,
    Question,
    SellerQuestion,
)
from fairmade.bundles.schemas import BundleRequest
from fairmade.forecasting.schemas import ForecastRequest
from fairmade.pricing.schemas import Contract
from fairmade.schemas import UTCResponse
from fairmade.seller_insights.schemas import InsightOptions
from fairmade.supplier_recommendations.schemas import RecommendationOptions

ConversationRevision = Annotated[int, Field(strict=True, ge=0, le=40)]


class SellerScope(Contract):
    role: Literal["seller"]
    product_id: UUID
    analysis_id: UUID | None = None
    supplier_report_id: UUID | None = None
    history_period: HistoryPeriod | None = None
    include_recipe_inputs: StrictBool = False
    recommendations: RecommendationOptions | None = None

    @model_validator(mode="after")
    def selected_supplier_report(self):
        if self.recommendations is not None and self.supplier_report_id is None:
            raise ValueError("Select supplier_report_id for recommendation options")
        return self

    insights: InsightOptions | None = None
    forecast: ForecastRequest | None = None
    bundles: BundleRequest | None = None


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
