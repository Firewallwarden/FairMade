"""Owner-only recipe edits and atomic recipe-to-analysis snapshots."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fairmade.analysis_records import build_analysis
from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.models import AccountRole, Product, ProductRecipe, RecipeCosting
from fairmade.ownership import require_owned_product
from fairmade.pricing.schemas import PricingRequest
from fairmade.pricing.service import calculate
from fairmade.recipes import repository
from fairmade.recipes.costing import CostLimitError, compile_recipe
from fairmade.recipes.schemas import (
    CostingRequest,
    CostingResult,
    RecipeCreate,
    RecipeData,
    RecipeReplacement,
)


def error(status: int, code: str, message: str) -> HTTPException:
    exception = api_error(status, code, message)
    exception.headers = {"Cache-Control": "no-store"}
    return exception


def require_recipe(db: Session, product_id: str) -> ProductRecipe:
    recipe = repository.recipe(db, product_id)
    if recipe is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return recipe


def lock_owned_product(db: Session, account_id: str, product_id: UUID) -> Product:
    require_owned_product(db, account_id, product_id)
    repository.reserve_product(db, str(product_id))
    if db.get(AccountRole, (account_id, "seller")) is None:
        raise error(403, "SELLER_REQUIRED", "Seller access is required.")
    return require_owned_product(db, account_id, product_id)


def checked_compilation(content: RecipeData) -> tuple[PricingRequest, CostingResult]:
    try:
        return compile_recipe(content)
    except CostLimitError:
        raise error(
            422, "COST_LIMIT_EXCEEDED", "An allocated ingredient cost exceeds the pricing limit."
        ) from None


def create(db: Session, account_id: str, product_id: UUID, body: RecipeCreate) -> ProductRecipe:
    product = lock_owned_product(db, account_id, product_id)
    content = RecipeData.model_validate(body.model_dump(mode="json"))
    checked_compilation(content)
    if repository.recipe(db, product.id) is not None:
        raise error(409, "RECIPE_EXISTS", "This product already has a recipe; reload and edit it.")
    recipe = ProductRecipe(
        product_id=product.id, revision=1, content=content.model_dump(mode="json")
    )
    db.add(recipe)
    db.commit()
    return recipe


def replace(
    db: Session, account_id: str, product_id: UUID, body: RecipeReplacement
) -> ProductRecipe:
    product = lock_owned_product(db, account_id, product_id)
    content = RecipeData.model_validate(body.model_dump(mode="json", exclude={"expected_revision"}))
    checked_compilation(content)
    recipe = require_recipe(db, product.id)
    if recipe.revision != body.expected_revision:
        raise error(409, "REVISION_CONFLICT", "The recipe changed; reload before editing.")
    recipe.content = content.model_dump(mode="json")
    recipe.revision += 1
    recipe.updated_at = utcnow()
    db.commit()
    return recipe


def save_costing(
    db: Session, account_id: str, product_id: UUID, body: CostingRequest
) -> tuple[RecipeCosting, bool]:
    product = lock_owned_product(db, account_id, product_id)
    previous = repository.retry(db, product.id, str(body.request_id))
    if previous is not None:
        if previous.recipe_revision != body.expected_revision:
            raise error(
                409, "IDEMPOTENCY_CONFLICT", "This request ID was used for another revision."
            )
        db.commit()
        return previous, False
    recipe = require_recipe(db, product.id)
    if recipe.revision != body.expected_revision:
        raise error(409, "REVISION_CONFLICT", "The recipe changed; reload before costing.")
    content = RecipeData.model_validate(recipe.content)
    inputs, allocations = checked_compilation(content)
    analysis = build_analysis(product, inputs, calculate(inputs))
    db.add(analysis)
    db.flush()
    costing = RecipeCosting(
        product_id=product.id,
        request_id=str(body.request_id),
        recipe_revision=recipe.revision,
        pricing_analysis_id=analysis.id,
        recipe_snapshot=recipe.content,
        result=allocations.model_dump(mode="json"),
    )
    db.add(costing)
    # Failure anywhere rolls back both the analysis and its recipe provenance.
    db.commit()
    return costing, True
