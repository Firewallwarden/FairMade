"""Revision-safe stock replacement without changing quantities already reserved."""

from sqlalchemy.orm import Session

from fairmade import stock
from fairmade.commerce_errors import conflict
from fairmade.database import utcnow
from fairmade.inventory.schemas import InventoryReplacement, InventoryResponse
from fairmade.models import SellableInventory


def get_inventory(db: Session, product_id: str) -> InventoryResponse:
    current = stock.balance(db, product_id, utcnow())
    return InventoryResponse(
        product_id=product_id,
        revision=current.revision,
        configured=current.revision > 0,
        selling_unit=current.selling_unit,
        on_hand=current.on_hand,
        reserved=current.reserved,
        available=current.available,
    )


def replace(
    db: Session,
    product_id: str,
    body: InventoryReplacement,
) -> InventoryResponse:
    stock.lock_products(db, [product_id])
    current = stock.balance(db, product_id, utcnow())
    if body.expected_revision != current.revision:
        raise conflict("REVISION_CONFLICT", "The inventory revision has changed.")
    if current.reserved > body.on_hand:
        raise conflict("STOCK_RESERVED", "On-hand stock cannot be below active reservations.")
    if current.selling_unit and current.selling_unit != body.selling_unit:
        if current.on_hand or current.reserved:
            raise conflict(
                "INVENTORY_UNIT_LOCKED", "Empty existing stock before changing its unit basis."
            )
    inventory = db.get(SellableInventory, product_id)
    if inventory is None:
        inventory = SellableInventory(product_id=product_id)
        db.add(inventory)
    inventory.revision = current.revision + 1
    inventory.selling_unit = body.selling_unit
    inventory.on_hand = body.on_hand
    db.commit()
    return get_inventory(db, product_id)
