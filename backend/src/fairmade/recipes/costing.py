"""Pure recipe allocation into the existing deterministic pricing contract."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from fairmade.pricing.schemas import BatchCost, CostCategory, PricingRequest
from fairmade.recipes.schemas import AllocatedIngredient, CostingResult, RecipeData
from fairmade.units import UNITS

MICRO = Decimal("0.000001")
MAX_COST = Decimal("1000000000")


class CostLimitError(ValueError):
    """An allocated line cannot fit the existing pricing contract."""


def compile_recipe(recipe: RecipeData) -> tuple[PricingRequest, CostingResult]:
    with localcontext() as context:
        context.prec = 50
        allocated = []
        warnings = [
            "Manual costs and quantities are unverified seller reports.",
            "Each consumed cost rounds half up to six decimal USD places before pricing.",
            "Consumed cost is allocated from purchases; it is not whole-package cash spending.",
            "No supplier quotes, quality claims, inventory consumption or market data are used.",
        ]
        for ingredient in recipe.ingredients:
            consumed = ingredient.quantity.value * UNITS[ingredient.quantity.unit][1]
            purchased = (
                ingredient.purchase_quantity.value * UNITS[ingredient.purchase_quantity.unit][1]
            )
            exact = ingredient.purchase_cost * consumed / purchased
            amount = exact.quantize(MICRO, rounding=ROUND_HALF_UP)
            if amount > MAX_COST:
                raise CostLimitError("Allocated ingredient cost exceeds the pricing limit")
            if exact > 0 and amount == 0:
                warnings.append("A positive ingredient allocation rounded to zero at six places.")
            allocated.append(AllocatedIngredient(label=ingredient.label, allocated_cost=amount))
        materials = [
            BatchCost(label=line.label, category=CostCategory.MATERIALS, amount=line.allocated_cost)
            for line in allocated
        ]
        inputs = PricingRequest(
            currency=recipe.currency,
            sellable_units=recipe.sellable_units,
            costs=materials + recipe.other_costs,
            labor=recipe.labor,
            payment_fees=recipe.payment_fees,
            target_margin=recipe.target_margin,
            proposed_prices=recipe.proposed_prices,
        )
        result = CostingResult(
            ingredients=allocated,
            materials_total=sum((line.allocated_cost for line in allocated), Decimal(0)),
            warnings=warnings,
        )
        return inputs, result
