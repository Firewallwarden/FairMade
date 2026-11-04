"""Compose approved listings and stock into atomic, retry-safe unpaid orders."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from fairmade import stock
from fairmade.commerce_errors import conflict, missing
from fairmade.database import utcnow
from fairmade.marketplace.repository import visible_listings
from fairmade.marketplace.schemas import CatalogContent
from fairmade.models import MarketplaceListing, Order, OrderLine, Product
from fairmade.orders import domain, repository
from fairmade.orders.schemas import CartPreview, CartRequest, OrderResponse, PricedLine
from fairmade.sales.cost_basis import save_order_snapshot
from fairmade.sales.costing import OrderCostLine


def _price_cart(
    db: Session,
    buyer_id: str,
    body: CartRequest,
    now: datetime,
) -> tuple[CartPreview, str, list[tuple[MarketplaceListing, PricedLine]]]:
    lines = []
    seller_ids = set()
    subtotal = 0
    for requested in sorted(body.items, key=lambda item: str(item.listing_id)):
        listing = db.scalar(
            visible_listings().where(MarketplaceListing.id == str(requested.listing_id))
        )
        if listing is None:
            raise missing()
        if listing.published_revision != requested.expected_listing_revision:
            raise conflict(
                "LISTING_CHANGED", "An approved listing revision has changed; review it again."
            )
        seller_id = db.get(Product, listing.product_id).account_id
        if seller_id == buyer_id:
            raise conflict("SELF_PURCHASE", "A seller cannot order their own product.")
        seller_ids.add(seller_id)
        current = stock.balance(db, listing.product_id, now)
        catalog = CatalogContent.model_validate(listing.public_payload)
        if current.revision == 0:
            raise conflict(
                "INVENTORY_NOT_CONFIGURED", "Sellable inventory has not been configured."
            )
        if current.selling_unit != catalog.product.selling_unit:
            raise conflict(
                "INVENTORY_UNIT_MISMATCH", "Inventory does not match the approved selling unit."
            )
        if current.available < requested.quantity:
            raise conflict("INSUFFICIENT_STOCK", "There is insufficient available stock.")
        line_minor = listing.price_minor * requested.quantity
        subtotal += line_minor
        if subtotal > domain.MAX_SUBTOTAL_MINOR:
            raise conflict(
                "ORDER_AMOUNT_LIMIT", "The merchandise subtotal exceeds the supported limit."
            )
        lines.append(
            (
                listing,
                PricedLine(
                    listing_id=listing.id,
                    published_revision=listing.published_revision,
                    quantity=requested.quantity,
                    unit_price=domain.money(listing.price_minor),
                    subtotal=domain.money(line_minor),
                    listing=catalog,
                ),
            )
        )
    if len(seller_ids) != 1:
        raise conflict("MULTIPLE_SELLERS", "Create a separate order for each seller.")
    return (
        CartPreview(
            items=[line for _listing, line in lines],
            subtotal=domain.money(subtotal),
            notices=list(domain.NOTICES),
        ),
        seller_ids.pop(),
        lines,
    )


def preview(db: Session, buyer_id: str, body: CartRequest) -> CartPreview:
    return _price_cart(db, buyer_id, body, utcnow())[0]


def create(
    db: Session,
    buyer_id: str,
    body: CartRequest,
    key: str,
) -> tuple[Order, bool]:
    stock.lock_for_listings(db, [str(line.listing_id) for line in body.items])
    requested_hash = domain.fingerprint(body)
    existing = repository.by_key(db, buyer_id, key)
    if existing is not None:
        if existing.request_hash != requested_hash:
            raise conflict(
                "IDEMPOTENCY_CONFLICT", "This key was already used for different order content."
            )
        db.commit()
        return existing, False
    now = utcnow()
    snapshot, seller_id, lines = _price_cart(db, buyer_id, body, now)
    order = Order(
        buyer_account_id=buyer_id,
        seller_account_id=seller_id,
        idempotency_key=key,
        request_hash=requested_hash,
        status="pending_payment",
        created_at=now,
        expires_at=now + timedelta(minutes=15),
        subtotal_minor=sum(listing.price_minor * line.quantity for listing, line in lines),
        snapshot=snapshot.model_dump(mode="json", exclude_none=True),
    )
    db.add(order)
    db.flush()
    db.add_all(
        [
            OrderLine(
                order_id=order.id,
                listing_id=listing.id,
                product_id=listing.product_id,
                quantity=line.quantity,
                unit_price_minor=listing.price_minor,
                subtotal_minor=listing.price_minor * line.quantity,
            )
            for listing, line in lines
        ]
    )
    save_order_snapshot(
        db,
        order,
        [
            OrderCostLine(
                listing_id=listing.id,
                product_id=listing.product_id,
                quantity=line.quantity,
                selling_unit=line.listing.product.selling_unit,
                product_type=line.listing.product.product_type,
            )
            for listing, line in lines
        ],
    )
    db.commit()
    return order, True


def get_order(db: Session, account_id: str, order_id: str, *, seller=False) -> Order:
    order = db.scalar(repository.owned(db, account_id, seller=seller).where(Order.id == order_id))
    if order is None:
        raise missing()
    return order


def response(order: Order) -> OrderResponse:
    deadline = (
        order.expires_at.replace(tzinfo=UTC)
        if order.expires_at.tzinfo is None
        else order.expires_at
    )
    return OrderResponse(
        id=order.id,
        status=domain.effective_status(
            order.status,
            deadline,
            utcnow(),
            order.checkout.state if order.checkout else None,
            order.refund_request.state if order.refund_request else None,
        ),
        created_at=order.created_at,
        expires_at=deadline,
        snapshot=order.snapshot,
    )


def cancel(db: Session, account_id: str, order_id: str, *, seller=False) -> Order:
    repository.lock_order(db, order_id, account_id, seller=seller)
    order = get_order(db, account_id, order_id, seller=seller)
    if response(order).status in (
        "paid",
        "capture_pending",
        "payment_review",
        "refund_pending",
        "refund_review",
        "refunded",
    ):
        raise conflict(
            "PAYMENT_REQUIRES_RECONCILIATION", "A paid or uncertain capture cannot be cancelled."
        )
    if response(order).status == "pending_payment":
        order.status = "cancelled"
    db.commit()
    return order
