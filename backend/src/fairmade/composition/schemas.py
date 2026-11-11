"""Seller-authored composition is distinct from private production recipes."""

from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from fairmade.pricing.schemas import Contract, Label
from fairmade.unit_pricing.schemas import SellingQuantity

Description = Annotated[str, Field(min_length=1, max_length=200)]


class Component(Contract):
    label: Label
    kind: Literal["ingredient", "material", "packaging", "other"]
    reported_role: Description | None = None
    reported_specification: Description | None = None
    declared_quantity: SellingQuantity | None = None

    @field_validator("label", "reported_role", "reported_specification")
    @classmethod
    def printable_declaration(cls, value):
        if value is not None and not value.isprintable():
            raise ValueError("Composition text must use printable characters")
        return value


class CompositionDisclosure(Contract):
    completeness: Literal["partial", "seller_declared_complete"] = "partial"
    items: Annotated[list[Component], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def distinct_components(self) -> Self:
        keys = [(item.kind, item.label.casefold()) for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("Use each component label only once per kind")
        return self
