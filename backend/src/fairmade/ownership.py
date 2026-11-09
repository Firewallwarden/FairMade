"""Shared ownership checks for private seller resources."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.models import AccountRole, Product


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


def reserve_owned_product(db: Session, account_id: str, product_id: UUID | str) -> Product:
    """Serialize a local product write, then refresh ownership and seller access."""
    product = require_owned_product(db, account_id, product_id)
    db.execute(
        update(Product)
        .where(Product.id == product.id)
        .values(updated_at=Product.updated_at)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()
    if db.get(AccountRole, (account_id, "seller")) is None:
        raise api_error(403, "SELLER_REQUIRED", "Seller access is required.")
    return require_owned_product(db, account_id, product_id)
