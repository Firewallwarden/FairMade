"""Atomic livestock profiles, membership changes and immutable retry-safe history."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.livestock import repository
from fairmade.livestock.schemas import (
    AnimalCreate,
    AnimalReplacement,
    AnimalResponse,
    GroupCreate,
    GroupProfile,
    GroupReplacement,
    GroupResponse,
    HistoryResponse,
)
from fairmade.models import (
    LivestockAnimal,
    LivestockAnimalEvent,
    LivestockGroup,
    LivestockGroupEvent,
)
from fairmade.ownership import reserve_seller_account


def error(status: int, code: str, message: str) -> HTTPException:
    exception = api_error(status, code, message)
    exception.headers = {"Cache-Control": "no-store"}
    return exception


def require_group(db: Session, account_id: str, resource_id: str) -> LivestockGroup:
    group = repository.group(db, account_id, resource_id)
    if group is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return group


def require_animal(db: Session, account_id: str, resource_id: str) -> LivestockAnimal:
    animal = repository.animal(db, account_id, resource_id)
    if animal is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return animal


def group_response(group: LivestockGroup, registered: int) -> GroupResponse:
    profile = GroupProfile.model_validate(group).model_dump()
    return GroupResponse(**profile, registered_active_animals=registered)


def history_response(event: LivestockGroupEvent | LivestockAnimalEvent) -> HistoryResponse:
    resource_id = event.group_id if isinstance(event, LivestockGroupEvent) else event.animal_id
    return HistoryResponse(
        id=event.id,
        resource_id=resource_id,
        request_id=event.request_id,
        revision=event.revision,
        occurred_on=event.occurred_on,
        reason=event.reason,
        before=event.before,
        after=event.after,
        created_at=event.created_at,
    )


def previous_change(
    db: Session,
    event_type: type[LivestockGroupEvent] | type[LivestockAnimalEvent],
    account_id: str,
    resource_id: str | None,
    body: GroupCreate | GroupReplacement | AnimalCreate | AnimalReplacement,
) -> LivestockGroupEvent | LivestockAnimalEvent | None:
    previous = db.scalar(
        select(event_type).where(
            event_type.account_id == account_id, event_type.request_id == str(body.request_id)
        )
    )
    if previous is None:
        return None
    previous_id = previous.group_id if event_type is LivestockGroupEvent else previous.animal_id
    if (
        resource_id is not None and previous_id != resource_id
    ) or previous.request != body.model_dump(mode="json"):
        raise error(409, "IDEMPOTENCY_CONFLICT", "This request ID was used for another change.")
    db.commit()
    return previous


def check_revision(current: int, expected: int) -> None:
    if current != expected:
        raise error(409, "REVISION_CONFLICT", "The record changed; reload before editing.")


def save_group(
    db: Session,
    account_id: str,
    body: GroupCreate | GroupReplacement,
    resource_id: str | None = None,
) -> tuple[LivestockGroupEvent, bool]:
    if resource_id is not None:
        require_group(db, account_id, resource_id)
    reserve_seller_account(db, account_id)
    previous = previous_change(db, LivestockGroupEvent, account_id, resource_id, body)
    if previous is not None:
        return previous, False
    now = utcnow()
    before = None
    if resource_id is None:
        group = LivestockGroup(
            account_id=account_id,
            species=body.species,
            species_key=body.species.casefold(),
            revision=1,
            created_at=now,
            updated_at=now,
        )
    else:
        group = require_group(db, account_id, resource_id)
        check_revision(group.revision, body.expected_revision)
        before = GroupProfile.model_validate(group).model_dump(mode="json")
        if body.archived and repository.registered_count(db, account_id, group.id):
            raise error(
                409, "GROUP_HAS_MEMBERS", "Move active animals before archiving this group."
            )
        group.revision += 1
    existing = db.scalar(
        select(LivestockGroup.id).where(
            LivestockGroup.account_id == account_id, LivestockGroup.name_key == body.name.casefold()
        )
    )
    if existing is not None and existing != group.id:
        raise error(409, "GROUP_EXISTS", "A group with this name already exists.")
    group.name = body.name
    group.name_key = body.name.casefold()
    group.breed = body.breed
    group.notes = body.notes
    group.reported_headcount = body.reported_headcount
    group.headcount_on = body.headcount_on
    group.archived = int(body.archived)
    group.updated_at = now
    db.add(group)
    db.flush()
    event = LivestockGroupEvent(
        account_id=account_id,
        group_id=group.id,
        request_id=str(body.request_id),
        revision=group.revision,
        occurred_on=body.occurred_on,
        reason=body.reason,
        request=body.model_dump(mode="json"),
        before=before,
        after=GroupProfile.model_validate(group).model_dump(mode="json"),
    )
    db.add(event)
    db.commit()
    return event, True


def save_animal(
    db: Session,
    account_id: str,
    body: AnimalCreate | AnimalReplacement,
    resource_id: str | None = None,
) -> tuple[LivestockAnimalEvent, bool]:
    if resource_id is not None:
        require_animal(db, account_id, resource_id)
    reserve_seller_account(db, account_id)
    previous = previous_change(db, LivestockAnimalEvent, account_id, resource_id, body)
    if previous is not None:
        return previous, False
    now = utcnow()
    before = None
    if resource_id is None:
        animal = LivestockAnimal(
            account_id=account_id,
            species=body.species,
            species_key=body.species.casefold(),
            revision=1,
            created_at=now,
            updated_at=now,
        )
    else:
        animal = require_animal(db, account_id, resource_id)
        check_revision(animal.revision, body.expected_revision)
        before = AnimalResponse.model_validate(animal).model_dump(mode="json")
        animal.revision += 1
    group_id = str(body.group_id) if body.group_id is not None else None
    if group_id is not None:
        group = require_group(db, account_id, group_id)
        if group.archived:
            raise error(409, "GROUP_ARCHIVED", "Select an active livestock group.")
        if group.species_key != animal.species_key:
            raise error(409, "SPECIES_MISMATCH", "Animal and group species must match.")
    existing = db.scalar(
        select(LivestockAnimal.id).where(
            LivestockAnimal.account_id == account_id,
            LivestockAnimal.identifier_key == body.identifier.casefold(),
        )
    )
    if existing is not None and existing != animal.id:
        raise error(409, "ANIMAL_EXISTS", "An animal with this identifier already exists.")
    for field in (
        "identifier",
        "name",
        "breed",
        "sex",
        "born_on",
        "acquired_on",
        "status",
        "notes",
    ):
        setattr(animal, field, getattr(body, field))
    animal.identifier_key = body.identifier.casefold()
    animal.group_id = group_id
    animal.updated_at = now
    db.add(animal)
    db.flush()
    event = LivestockAnimalEvent(
        account_id=account_id,
        animal_id=animal.id,
        request_id=str(body.request_id),
        revision=animal.revision,
        occurred_on=body.occurred_on,
        reason=body.reason,
        request=body.model_dump(mode="json"),
        before=before,
        after=AnimalResponse.model_validate(animal).model_dump(mode="json"),
    )
    db.add(event)
    db.commit()
    return event, True
