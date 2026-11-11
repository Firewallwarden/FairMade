"""Explicit request scope, cited model paragraphs and authoritative evidence."""

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.cost_calendar.schemas import CalendarOptions
from fairmade.evidence import Amount
from fairmade.pricing.schemas import Contract
from fairmade.seller_insights.schemas import InsightOptions

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


class BuyerQuestion(Contract):
    question: Question
    listing_ids: Annotated[list[UUID], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def unique_listings(self) -> Self:
        if len(set(self.listing_ids)) != len(self.listing_ids):
            raise ValueError("Select each listing only once")
        return self


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
