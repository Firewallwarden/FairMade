"""Owner-scoped record lookup and bounded summary projections."""

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from fairmade.models import ProductionRecord


def get(db: Session, product_id: str, record_id: str) -> ProductionRecord | None:
    return db.scalar(
        select(ProductionRecord).where(
            ProductionRecord.product_id == product_id, ProductionRecord.id == record_id
        )
    )


def retry(db: Session, product_id: str, request_id: str) -> ProductionRecord | None:
    return db.scalar(
        select(ProductionRecord).where(
            ProductionRecord.product_id == product_id, ProductionRecord.request_id == request_id
        )
    )


def successor(db: Session, record_id: str) -> str | None:
    return db.scalar(
        select(ProductionRecord.id).where(ProductionRecord.corrects_record_id == record_id)
    )


def page(
    db: Session, product_id: str, include_corrected: bool, limit: int, offset: int
) -> list[dict]:
    record = ProductionRecord
    # Avoid reading large private cost/input blobs for summary pages.
    statement = select(
        record.id,
        record.product_id,
        record.request_id,
        record.label,
        record.kind,
        record.started_on,
        record.completed_on,
        record.selling_unit,
        record.total_units,
        record.sellable_units,
        record.corrects_record_id,
        record.created_at,
    ).where(record.product_id == product_id)
    if not include_corrected:
        correction = aliased(ProductionRecord)
        has_correction = (
            select(correction.id).where(correction.corrects_record_id == record.id).exists()
        )
        statement = statement.where(~has_correction)
    rows = db.execute(
        statement.order_by(record.completed_on.desc(), record.created_at.desc(), record.id.desc())
        .limit(limit)
        .offset(offset)
    ).mappings()
    return [dict(row) for row in rows]
