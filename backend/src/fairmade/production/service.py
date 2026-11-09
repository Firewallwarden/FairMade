"""Immutable completed records and linear, explicit correction history."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.models import ProductionRecord
from fairmade.ownership import reserve_owned_product
from fairmade.production import repository
from fairmade.production.costing import calculate_completed
from fairmade.production.schemas import ProductionRequest
from fairmade.schemas import ProductResponse


def error(status: int, code: str, message: str) -> HTTPException:
    exception = api_error(status, code, message)
    exception.headers = {"Cache-Control": "no-store"}
    return exception


def require_record(db: Session, product_id: str, record_id: str) -> ProductionRecord:
    record = repository.get(db, product_id, record_id)
    if record is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return record


def save(
    db: Session, account_id: str, product_id: UUID, body: ProductionRequest
) -> tuple[ProductionRecord, bool]:
    product = reserve_owned_product(db, account_id, product_id)
    previous = repository.retry(db, product.id, str(body.request_id))
    if previous is not None:
        if ProductionRequest.model_validate(previous.request) != body:
            raise error(409, "IDEMPOTENCY_CONFLICT", "This request ID was used for another record.")
        db.commit()
        return previous, False
    corrects_id = str(body.corrects_record_id) if body.corrects_record_id else None
    if corrects_id is not None:
        prior = require_record(db, product.id, corrects_id)
        if repository.successor(db, prior.id) is not None:
            raise error(
                409,
                "RECORD_ALREADY_CORRECTED",
                "Correct the latest record in this history.",
            )
        snapshot = prior.product_snapshot
    else:
        snapshot = ProductResponse.model_validate(product).model_dump(mode="json")
    if body.selling_unit != snapshot["selling_unit"]:
        raise error(
            409, "PRODUCTION_UNIT_MISMATCH", "Output unit must match the record's product basis."
        )
    result = calculate_completed(body)
    record = ProductionRecord(
        product_id=product.id,
        request_id=str(body.request_id),
        label=body.label,
        kind=body.kind,
        started_on=body.started_on,
        completed_on=body.completed_on,
        selling_unit=body.selling_unit,
        total_units=body.total_units,
        sellable_units=body.sellable_units,
        corrects_record_id=corrects_id,
        product_snapshot=snapshot,
        request=body.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )
    db.add(record)
    db.commit()
    return record, True
