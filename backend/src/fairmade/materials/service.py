"""Manual ledger transactions; no cost, recipe, supplier or order side effects."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.materials import quantities, repository
from fairmade.materials.schemas import (
    MaterialCreate,
    MaterialReplacement,
    MaterialResponse,
    MovementRequest,
    MovementResponse,
)
from fairmade.models import AccountRole, Material, MaterialMovement


def error(status: int, code: str, message: str) -> HTTPException:
    exception = api_error(status, code, message)
    exception.headers = {"Cache-Control": "no-store"}
    return exception


def require_owned(db: Session, account_id: str, material_id: str) -> Material:
    material = repository.owned(db, account_id, material_id)
    if material is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return material


def lock_account(db: Session, account_id: str) -> None:
    repository.reserve_account(db, account_id)
    if db.get(AccountRole, (account_id, "seller")) is None:
        raise error(403, "SELLER_REQUIRED", "Seller access is required.")


def lock_owned(db: Session, account_id: str, material_id: str) -> Material:
    require_owned(db, account_id, material_id)
    lock_account(db, account_id)
    return require_owned(db, account_id, material_id)


def material_response(material: Material) -> MaterialResponse:
    return MaterialResponse(
        id=material.id,
        name=material.name,
        notes=material.notes,
        unit=material.unit,
        on_hand=quantities.display(material.on_hand_micros),
        revision=material.revision,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


def movement_response(movement: MaterialMovement) -> MovementResponse:
    return MovementResponse(
        id=movement.id,
        material_id=movement.material_id,
        request_id=movement.request_id,
        revision=movement.revision,
        kind=movement.kind,
        material_name=movement.material_name,
        unit=movement.unit,
        before=quantities.display(movement.before_micros),
        after=quantities.display(movement.after_micros),
        delta=quantities.display(movement.after_micros - movement.before_micros),
        request=movement.request,
        created_at=movement.created_at,
    )


def create(db: Session, account_id: str, body: MaterialCreate) -> Material:
    lock_account(db, account_id)
    key = body.name.casefold()
    if repository.named(db, account_id, key) is not None:
        raise error(409, "MATERIAL_EXISTS", "A material with this name already exists.")
    material = Material(
        account_id=account_id,
        name=body.name,
        name_key=key,
        notes=body.notes,
        unit=body.unit,
        on_hand_micros=0,
        revision=1,
    )
    db.add(material)
    db.commit()
    return material


def replace(db: Session, account_id: str, material_id: str, body: MaterialReplacement) -> Material:
    material = lock_owned(db, account_id, material_id)
    if material.revision != body.expected_revision:
        raise error(409, "REVISION_CONFLICT", "The material changed; reload before editing.")
    key = body.name.casefold()
    existing = repository.named(db, account_id, key)
    if existing is not None and existing.id != material.id:
        raise error(409, "MATERIAL_EXISTS", "A material with this name already exists.")
    material.name = body.name
    material.name_key = key
    material.notes = body.notes
    material.revision += 1
    material.updated_at = utcnow()
    db.commit()
    return material


def record(
    db: Session, account_id: str, material_id: str, body: MovementRequest
) -> tuple[MaterialMovement, bool]:
    material = lock_owned(db, account_id, material_id)
    previous = repository.retry(db, material.id, str(body.request_id))
    if previous is not None:
        if MovementRequest.model_validate(previous.request) != body:
            raise error(
                409, "IDEMPOTENCY_CONFLICT", "This request ID was used for another movement."
            )
        db.commit()
        return previous, False
    if material.revision != body.expected_revision:
        raise error(409, "REVISION_CONFLICT", "The material changed; reload before recording.")
    try:
        amount = quantities.normalize(body.quantity, body.unit, material.unit)
    except quantities.QuantityError as exc:
        raise error(422, exc.code, str(exc)) from None
    try:
        after = quantities.next_balance(material.on_hand_micros, amount, body.kind)
    except quantities.QuantityError as exc:
        raise error(409, exc.code, str(exc)) from None
    movement = MaterialMovement(
        material_id=material.id,
        request_id=str(body.request_id),
        revision=material.revision + 1,
        kind=body.kind,
        material_name=material.name,
        unit=material.unit,
        before_micros=material.on_hand_micros,
        after_micros=after,
        request=body.model_dump(mode="json"),
    )
    material.on_hand_micros = after
    material.revision += 1
    material.updated_at = utcnow()
    db.add(movement)
    db.commit()
    return movement, True
