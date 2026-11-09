"""Owner-scoped, indexed material queries and a local SQLite write reservation."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.models import Account, Material, MaterialMovement


def reserve_account(db: Session, account_id: str) -> None:
    # Serializes name uniqueness checks, revisions and ledger writes. No account
    # metadata changes; expire earlier reads before rechecking roles and balances.
    db.execute(
        update(Account)
        .where(Account.id == account_id)
        .values(created_at=Account.created_at)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()


def owned(db: Session, account_id: str, material_id: str) -> Material | None:
    return db.scalar(
        select(Material).where(Material.id == material_id, Material.account_id == account_id)
    )


def named(db: Session, account_id: str, name_key: str) -> Material | None:
    return db.scalar(
        select(Material).where(Material.account_id == account_id, Material.name_key == name_key)
    )


def materials(db: Session, account_id: str, limit: int, offset: int) -> list[Material]:
    return list(
        db.scalars(
            select(Material)
            .where(Material.account_id == account_id)
            .order_by(Material.created_at.desc(), Material.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def retry(db: Session, material_id: str, request_id: str) -> MaterialMovement | None:
    return db.scalar(
        select(MaterialMovement).where(
            MaterialMovement.material_id == material_id, MaterialMovement.request_id == request_id
        )
    )


def movement(db: Session, material_id: str, movement_id: str) -> MaterialMovement | None:
    return db.scalar(
        select(MaterialMovement).where(
            MaterialMovement.material_id == material_id, MaterialMovement.id == movement_id
        )
    )


def movements(db: Session, material_id: str, limit: int, offset: int) -> list[MaterialMovement]:
    return list(
        db.scalars(
            select(MaterialMovement)
            .where(MaterialMovement.material_id == material_id)
            .order_by(MaterialMovement.revision.desc(), MaterialMovement.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
