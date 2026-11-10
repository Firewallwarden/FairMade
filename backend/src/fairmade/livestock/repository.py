"""Bounded owner-scoped queries; group counts are not inferred population totals."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fairmade.models import (
    LivestockAnimal,
    LivestockAnimalEvent,
    LivestockGroup,
    LivestockGroupEvent,
)


def group(db: Session, account_id: str, resource_id: str) -> LivestockGroup | None:
    return db.scalar(
        select(LivestockGroup).where(
            LivestockGroup.account_id == account_id, LivestockGroup.id == resource_id
        )
    )


def animal(db: Session, account_id: str, resource_id: str) -> LivestockAnimal | None:
    return db.scalar(
        select(LivestockAnimal).where(
            LivestockAnimal.account_id == account_id, LivestockAnimal.id == resource_id
        )
    )


def registered_count(db: Session, account_id: str, group_id: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(LivestockAnimal)
        .where(
            LivestockAnimal.account_id == account_id,
            LivestockAnimal.group_id == group_id,
            LivestockAnimal.status == "active",
        )
    )


def groups(db: Session, account_id: str, archived: bool | None, limit: int, offset: int):
    counts = (
        select(
            LivestockAnimal.group_id,
            func.count().label("registered"),
        )
        .where(
            LivestockAnimal.account_id == account_id,
            LivestockAnimal.status == "active",
            LivestockAnimal.group_id.is_not(None),
        )
        .group_by(LivestockAnimal.group_id)
        .subquery()
    )
    query = (
        select(LivestockGroup, func.coalesce(counts.c.registered, 0))
        .outerjoin(counts, counts.c.group_id == LivestockGroup.id)
        .where(LivestockGroup.account_id == account_id)
    )
    if archived is not None:
        query = query.where(LivestockGroup.archived == archived)
    return db.execute(
        query.order_by(LivestockGroup.created_at.desc(), LivestockGroup.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()


def animals(
    db: Session,
    account_id: str,
    group_id: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> list[LivestockAnimal]:
    query = select(LivestockAnimal).where(LivestockAnimal.account_id == account_id)
    if group_id is not None:
        query = query.where(LivestockAnimal.group_id == group_id)
    if status is not None:
        query = query.where(LivestockAnimal.status == status)
    return list(
        db.scalars(
            query.order_by(LivestockAnimal.created_at.desc(), LivestockAnimal.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def group_history(db: Session, group_id: str, limit: int, offset: int) -> list[LivestockGroupEvent]:
    return list(
        db.scalars(
            select(LivestockGroupEvent)
            .where(LivestockGroupEvent.group_id == group_id)
            .order_by(LivestockGroupEvent.revision.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def animal_history(
    db: Session, animal_id: str, limit: int, offset: int
) -> list[LivestockAnimalEvent]:
    return list(
        db.scalars(
            select(LivestockAnimalEvent)
            .where(LivestockAnimalEvent.animal_id == animal_id)
            .order_by(LivestockAnimalEvent.revision.desc())
            .limit(limit)
            .offset(offset)
        )
    )
