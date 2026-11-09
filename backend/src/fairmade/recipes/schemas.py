"""Manual quantities and purchase allocations; no supplier or stock coupling."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from fairmade.evidence import Amount, PositiveAmount, today
from fairmade.pricing.schemas import (
    BatchCost,
    Contract,
    CostCategory,
    Count,
    Label,
    Labor,
    MarginTargets,
    PaymentFees,
)
from fairmade.publication import Revision
from fairmade.schemas import UTCResponse
from fairmade.units import UNITS


class RecipeQuantity(Contract):
    value: PositiveAmount
    unit: Literal["g", "kg", "ml", "l", "item"]

    @model_validator(mode="after")
    def whole_items(self) -> Self:
        if self.unit == "item" and self.value != self.value.to_integral_value():
            raise ValueError("Item quantities must be whole numbers")
        return self


class Ingredient(Contract):
    label: Label
    quantity: RecipeQuantity = Field(description="Raw quantity consumed, including batch waste.")
    purchase_quantity: RecipeQuantity
    purchase_cost: Amount = Field(description="USD cost of the stated purchase quantity.")
    cost_recorded_on: date

    @model_validator(mode="after")
    def compatible_units(self) -> Self:
        if UNITS[self.quantity.unit][0] != UNITS[self.purchase_quantity.unit][0]:
            raise ValueError("Consumed and purchased quantities must have compatible dimensions")
        return self


class RecipeData(Contract):
    name: Label
    currency: Literal["USD"]
    sellable_units: Count
    ingredients: Annotated[list[Ingredient], Field(min_length=1, max_length=100)]
    other_costs: Annotated[list[BatchCost], Field(max_length=100)]
    labor: Annotated[list[Labor], Field(max_length=100)]
    payment_fees: PaymentFees
    target_margin: MarginTargets
    proposed_prices: Annotated[list[Amount], Field(max_length=50)] = Field(default_factory=list)
    instructions: Annotated[str, Field(max_length=10000)] = ""

    @model_validator(mode="after")
    def unambiguous_costs(self) -> Self:
        labels = [ingredient.label.casefold() for ingredient in self.ingredients]
        if len(labels) != len(set(labels)):
            raise ValueError("Ingredient labels must be distinct")
        if any(cost.category == CostCategory.MATERIALS for cost in self.other_costs):
            raise ValueError("Material costs belong in ingredients, not other_costs")
        if self.payment_fees.rate + self.target_margin.maximum >= 1:
            raise ValueError("Processing rate plus maximum target margin must be less than 1")
        return self


class RecipeCreate(RecipeData):
    @model_validator(mode="after")
    def no_future_cost(self) -> Self:
        if any(ingredient.cost_recorded_on > today() for ingredient in self.ingredients):
            raise ValueError("Cost recording dates cannot be in the future")
        return self


class RecipeReplacement(RecipeCreate):
    expected_revision: Revision


class RecipeResponse(UTCResponse):
    product_id: UUID
    revision: int
    content: RecipeData
    created_at: datetime
    updated_at: datetime


class CostingRequest(Contract):
    expected_revision: Revision
    request_id: UUID = Field(description="Client-generated retry key, scoped to this product.")


class AllocatedIngredient(Contract):
    label: str
    allocated_cost: Decimal


class CostingResult(Contract):
    calculation_version: Literal["manual-recipe-costing-v1"] = "manual-recipe-costing-v1"
    currency: Literal["USD"] = "USD"
    basis: Literal["seller_reported_unverified"] = "seller_reported_unverified"
    ingredients: list[AllocatedIngredient]
    materials_total: Decimal
    warnings: list[str]


class CostingSummary(UTCResponse):
    id: UUID
    product_id: UUID
    request_id: UUID
    recipe_revision: int
    pricing_analysis_id: UUID
    created_at: datetime


class CostingResponse(CostingSummary):
    # Return historical JSON without depending on a future recipe schema.
    recipe_snapshot: dict
    result: dict
