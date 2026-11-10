"""Small queries and a SQLite write reservation for recipe transactions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.models import ProductRecipe, RecipeCosting


def recipe(db: Session, product_id: str) -> ProductRecipe | None:
    return db.get(ProductRecipe, product_id)


def retry(db: Session, product_id: str, request_id: str) -> RecipeCosting | None:
    return db.scalar(
        select(RecipeCosting).where(
            RecipeCosting.product_id == product_id, RecipeCosting.request_id == request_id
        )
    )


def costing(db: Session, product_id: str, costing_id: str) -> RecipeCosting | None:
    return db.scalar(
        select(RecipeCosting).where(
            RecipeCosting.product_id == product_id, RecipeCosting.id == costing_id
        )
    )


def page(db: Session, product_id: str, limit: int, offset: int) -> list[RecipeCosting]:
    return list(
        db.scalars(
            select(RecipeCosting)
            .where(RecipeCosting.product_id == product_id)
            .order_by(RecipeCosting.created_at.desc(), RecipeCosting.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
