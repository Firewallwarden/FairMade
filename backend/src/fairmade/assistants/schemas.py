"""Explicit request scope, cited model paragraphs and authoritative evidence."""

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from fairmade.baskets.schemas import BasketRequest
from fairmade.bundles.schemas import BundleRequest
from fairmade.cost_calendar.schemas import CalendarOptions
from fairmade.evidence import Amount
from fairmade.forecasting.schemas import ForecastRequest
from fairmade.pricing.schemas import Contract
from fairmade.seller_insights.schemas import InsightOptions
from fairmade.supplier_recommendations.schemas import RecommendationOptions

Question = Annotated[str, Field(min_length=1, max_length=2000)]
EvidenceKey = Annotated[str, Field(pattern=r"^e[1-9][0-9]?$")]


class HistoryPeriod(Contract):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def bounded_period(self) -> Self:
        if not 1 <= (self.end_date - self.start_date).days <= 366:
            raise ValueError("Use an exclusive end date, 1-366 days after start")
        return self


class SellerQuestion(Contract):
    question: Question
    product_id: UUID
    analysis_id: UUID | None = None
    supplier_report_id: UUID | None = None
    history_period: HistoryPeriod | None = None
    insights: InsightOptions | None = None
    cost_calendar: CalendarOptions | None = None
    bundles: BundleRequest | None = None
    forecast: ForecastRequest | None = None
    recommendations: RecommendationOptions | None = None

    @model_validator(mode="after")
    def selected_supplier_report(self) -> Self:
        if self.recommendations is not None and self.supplier_report_id is None:
            raise ValueError("Select supplier_report_id for recommendation options")
        return self

    include_recipe_inputs: StrictBool = False
    pricing_review_id: UUID | None = None


class BuyerSelection(Contract):
    listing_ids: Annotated[list[UUID], Field(max_length=4)] = Field(default_factory=list)
    basket: BasketRequest | None = None
    bundles: BundleRequest | None = None

    @model_validator(mode="after")
    def unique_listings(self) -> Self:
        if len(set(self.listing_ids)) != len(self.listing_ids):
            raise ValueError("Select each listing only once")
        if sum((bool(self.listing_ids), self.basket is not None, self.bundles is not None)) != 1:
            raise ValueError("Choose exactly one listing_ids, basket or bundles scope")
        return self


class BuyerQuestion(BuyerSelection):
    question: Question


class ScenarioPlan(Contract):
    proposed_prices: Annotated[list[Amount], Field(max_length=5)]


class Paragraph(Contract):
    text: Annotated[str, Field(min_length=1, max_length=1200)]
    evidence_keys: Annotated[list[EvidenceKey], Field(min_length=1, max_length=8)]


class AnswerDraft(Contract):
    paragraphs: Annotated[list[Paragraph], Field(min_length=1, max_length=4)]


class Evidence(Contract):
    key: EvidenceKey
    title: str
    basis: str
    data: dict


class AssistantResponse(Contract):
    assistant_version: Literal["fairmade-assistant-v1"] = "fairmade-assistant-v1"
    role: Literal["seller", "buyer"]
    provider: Literal["ollama_local"] = "ollama_local"
    model: Literal["qwen3:8b"] = "qwen3:8b"
    generated_at: datetime
    facts: list[Paragraph]
    paragraphs: list[Paragraph]
    evidence: list[Evidence]
    notices: list[str]
