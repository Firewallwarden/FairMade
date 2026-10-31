"""Shared ownership checks for private seller resources."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.models import Product


def require_owned_product(db: Session, account_id: str, product_id: UUID | str) -> Product:
    product = db.scalar(
        select(Product).where(
            Product.id == str(product_id),
            Product.account_id == account_id,
        )
    )
    if product is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return product
