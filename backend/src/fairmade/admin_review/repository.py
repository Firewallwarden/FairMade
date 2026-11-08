"""Bounded administrator views and serialized application/role changes."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from fairmade.models import Account, AccountRole, SellerApplication


def get(db: Session, application_id: str) -> SellerApplication | None:
    return db.scalar(
        select(SellerApplication)
        .options(joinedload(SellerApplication.decision))
        .where(SellerApplication.id == application_id)
    )


def reserve(db: Session, application_id: str) -> None:
    db.execute(
        update(SellerApplication)
        .where(SellerApplication.id == application_id)
        .values(revision=SellerApplication.revision)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()


def has_role(db: Session, account_id: str, role: str) -> bool:
    return db.get(AccountRole, (account_id, role)) is not None


def page(db: Session, state: str, limit: int, offset: int):
    statement = select(SellerApplication, Account.email).join(
        Account, Account.id == SellerApplication.account_id
    )
    statement = statement.options(joinedload(SellerApplication.decision))
    if state != "all":
        statement = statement.where(SellerApplication.status == state)
    return db.execute(
        statement.order_by(SellerApplication.submitted_at, SellerApplication.id)
        .limit(limit)
        .offset(offset)
    ).all()
