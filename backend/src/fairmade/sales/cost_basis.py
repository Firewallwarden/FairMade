"""Explicit seller selections and private snapshots in the order transaction."""

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.models import Analysis, Order, OrderSalesCostSnapshot, Product, ProductSalesCostBasis
from fairmade.sales.costing import OrderCostLine, cost_source, source_matches, total_production_cost
from fairmade.sales.schemas import CostBasisResponse, SelectCostBasis
from fairmade.schemas import UTCResponse


def current(db: Session, product_id: str) -> CostBasisResponse:
    selection = db.get(ProductSalesCostBasis, product_id)
    return CostBasisResponse(
        product_id=product_id,
        revision=selection.revision if selection else 0,
        analysis_id=selection.analysis_id if selection else None,
        source_snapshot=selection.source_snapshot if selection else None,
    )


def select_basis(db: Session, product: Product, body: SelectCostBasis) -> CostBasisResponse:
    # This write serializes against order creation's existing stock transaction.
    db.execute(
        insert(ProductSalesCostBasis)
        .values(product_id=product.id, revision=0, analysis_id=None, source_snapshot=None)
        .on_conflict_do_nothing(index_elements=["product_id"])
    )
    source = None
    if body.analysis_id is not None:
        analysis = db.scalar(
            select(Analysis).where(
                Analysis.id == str(body.analysis_id), Analysis.product_id == product.id
            )
        )
        if analysis is None:
            raise api_error(404, "NOT_FOUND", "Resource not found.")
        if analysis.calculation_version != "production-economics-v1":
            raise api_error(409, "COST_VERSION_UNSUPPORTED", "Select a supported cost analysis.")
        source = cost_source(
            analysis.inputs,
            analysis.product_snapshot,
            analysis.id,
            UTCResponse.utc_timestamp(analysis.created_at).isoformat(),
        )
        db.refresh(product)
        if not source_matches(source, product.selling_unit, product.product_type):
            raise api_error(
                409,
                "COST_UNIT_MISMATCH",
                "The analysis does not match this product's unit and type.",
            )
    changed = db.execute(
        update(ProductSalesCostBasis)
        .where(
            ProductSalesCostBasis.product_id == product.id,
            ProductSalesCostBasis.revision == body.expected_revision,
        )
        .values(
            revision=body.expected_revision + 1,
            analysis_id=str(body.analysis_id) if body.analysis_id else None,
            source_snapshot=source,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise api_error(
            409, "REVISION_CONFLICT", "The selected cost basis changed; reload and retry."
        )
    db.commit()
    db.expire_all()
    return current(db, product.id)


def save_order_snapshot(db: Session, order: Order, lines: list[OrderCostLine]) -> None:
    """Called once inside order creation; repeated order keys return before here."""
    product_ids = [line.product_id for line in lines]
    selections = db.scalars(
        select(ProductSalesCostBasis).where(ProductSalesCostBasis.product_id.in_(product_ids))
    ).all()
    by_product = {selection.product_id: selection for selection in selections}
    items = []
    for line in lines:
        selection = by_product.get(line.product_id)
        source = selection.source_snapshot if selection else None
        reason = None
        if source is None:
            reason = "COST_BASIS_NOT_SELECTED"
        elif not source_matches(source, line.selling_unit, line.product_type):
            reason = "COST_BASIS_UNIT_OR_TYPE_MISMATCH"
        items.append(
            {
                "listing_id": line.listing_id,
                "product_id": line.product_id,
                "quantity": line.quantity,
                "selling_unit": line.selling_unit,
                "product_type": line.product_type,
                "selection_revision": selection.revision if selection else 0,
                "source": source,
                "unavailable_reason": reason,
            }
        )
    total = total_production_cost(items)
    db.add(
        OrderSalesCostSnapshot(
            order_id=order.id,
            status="available" if total is not None else "unavailable",
            estimated_cost=str(total) if total is not None else None,
            details={
                "snapshot_version": "sale-cost-snapshot-v1",
                "basis": "seller_supplied_unverified",
                "items": items,
            },
        )
    )
