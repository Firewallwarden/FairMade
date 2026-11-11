"""Bounded owner-only source projections, excluding text not needed for insight calculations."""

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from fairmade.auth import api_error
from fairmade.models import Analysis, Material, MaterialMovement, ProductionRecord
from fairmade.seller_insights.records import CostObservation


def bounded(rows, maximum: int):
    if len(rows) > maximum:
        raise api_error(409, "INSIGHT_SCOPE_TOO_LARGE", "Narrow the insight period.")
    return rows


def analysis(db: Session, product_id: str, identifier: str | None) -> Analysis | None:
    query = select(Analysis).where(Analysis.product_id == product_id)
    if identifier:
        query = query.where(Analysis.id == identifier)
    result = db.scalar(query.order_by(Analysis.created_at.desc(), Analysis.id.desc()).limit(1))
    if identifier and result is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return result


def costs(db: Session, product_id: str, start: date, end: date) -> list[CostObservation]:
    rows = bounded(
        db.execute(
            select(
                Analysis.id,
                Analysis.created_at,
                Analysis.calculation_version,
                Analysis.product_snapshot["product_type"].as_string(),
                Analysis.product_snapshot["selling_unit"].as_string(),
                Analysis.result["costs"]["unit_cost"].as_string(),
            )
            .where(
                Analysis.product_id == product_id,
                Analysis.created_at >= datetime.combine(start, time.min),
                Analysis.created_at < datetime.combine(end, time.min),
            )
            .order_by(Analysis.created_at, Analysis.id)
            .limit(26)
        ).all(),
        25,
    )
    return [
        CostObservation(
            identifier=identifier,
            created_on=created.date(),
            product_type=kind,
            selling_unit=unit,
            unit_cost=Decimal(cost)
            if cost is not None and version == "production-economics-v1"
            else None,
        )
        for identifier, created, version, kind, unit, cost in rows
    ]


def production(db: Session, product_id: str, start: date, end: date) -> list:
    record = ProductionRecord
    correction = aliased(ProductionRecord)
    corrected = select(correction.id).where(correction.corrects_record_id == record.id).exists()
    return bounded(
        db.execute(
            select(
                record.selling_unit,
                record.total_units,
                record.sellable_units,
                record.product_snapshot["product_type"].as_string(),
            )
            .where(
                record.product_id == product_id,
                record.completed_on >= start,
                record.completed_on < end,
                ~corrected,
            )
            .order_by(record.id)
            .limit(101)
        ).all(),
        100,
    )


def waste(db: Session, account_id: str, start: date, end: date) -> list:
    occurred = MaterialMovement.request["occurred_on"].as_string()
    return bounded(
        db.execute(
            select(
                Material.id,
                Material.name,
                MaterialMovement.unit,
                MaterialMovement.before_micros,
                MaterialMovement.after_micros,
            )
            .join(Material, Material.id == MaterialMovement.material_id)
            .where(
                Material.account_id == account_id,
                MaterialMovement.kind == "waste",
                occurred >= start.isoformat(),
                occurred < end.isoformat(),
            )
            .order_by(MaterialMovement.id)
            .limit(201)
        ).all(),
        200,
    )
