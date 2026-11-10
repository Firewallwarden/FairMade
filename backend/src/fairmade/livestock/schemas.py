"""Explicit livestock identities, observed counts and versioned changes."""

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from fairmade.evidence import today
from fairmade.pricing.schemas import Contract, Label
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse

Notes = Annotated[str, Field(max_length=2000)]
Headcount = Annotated[int, Field(strict=True, ge=0, le=1_000_000)]
AnimalStatus = Literal["active", "departed", "deceased"]


class Change(Contract):
    request_id: UUID
    occurred_on: date
    reason: Annotated[str, Field(min_length=1, max_length=2000)]

    @model_validator(mode="after")
    def valid_change(self) -> Self:
        if self.occurred_on > today():
            raise ValueError("Change date cannot be in the future")
        if "\x00" in self.reason:
            raise ValueError("Reason cannot contain null characters")
        return self


class GroupFields(Contract):
    name: Label
    breed: Label | None = None
    notes: Notes | None = None
    reported_headcount: Headcount | None = None
    headcount_on: date | None = None
    archived: StrictBool = False

    @model_validator(mode="after")
    def dated_count(self) -> Self:
        if (self.reported_headcount is None) != (self.headcount_on is None):
            raise ValueError("A reported headcount requires its observation date")
        if self.headcount_on is not None and self.headcount_on > today():
            raise ValueError("Headcount date cannot be in the future")
        return self


class GroupCreate(GroupFields, Change):
    species: Label


class GroupReplacement(GroupFields, Change):
    expected_revision: Revision


class GroupProfile(UTCResponse):
    id: UUID
    name: str
    species: str
    breed: str | None
    notes: str | None
    reported_headcount: int | None
    headcount_on: date | None
    archived: bool
    revision: int
    created_at: datetime
    updated_at: datetime
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"


class GroupResponse(GroupProfile):
    registered_active_animals: int


class AnimalFields(Contract):
    identifier: Label
    name: Label | None = None
    breed: Label | None = None
    sex: Literal["unknown", "female", "male"] = "unknown"
    born_on: date | None = None
    acquired_on: date | None = None
    status: AnimalStatus = "active"
    group_id: UUID | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def consistent_animal(self) -> Self:
        for value in (self.born_on, self.acquired_on):
            if value is not None and value > today():
                raise ValueError("Animal dates cannot be in the future")
        if self.born_on and self.acquired_on and self.born_on > self.acquired_on:
            raise ValueError("Acquisition cannot precede birth")
        if self.status != "active" and self.group_id is not None:
            raise ValueError("Departed or deceased animals must leave their current group")
        return self


class AnimalCreate(AnimalFields, Change):
    species: Label


class AnimalReplacement(AnimalFields, Change):
    expected_revision: Revision


class AnimalResponse(UTCResponse):
    id: UUID
    identifier: str
    name: str | None
    species: str
    breed: str | None
    sex: Literal["unknown", "female", "male"]
    born_on: date | None
    acquired_on: date | None
    status: AnimalStatus
    group_id: UUID | None
    notes: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"


class HistoryResponse(UTCResponse):
    id: UUID
    resource_id: UUID
    request_id: UUID
    revision: int
    occurred_on: date
    reason: str
    before: dict | None
    after: dict
    created_at: datetime
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"


class LivestockReference(Contract):
    kind: Literal["group", "animal"]
    id: UUID
    expected_revision: Revision
