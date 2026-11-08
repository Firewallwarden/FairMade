"""Local database-operator bootstrap for the initial administrator only; never HTTP."""

import argparse
import sys
from typing import Annotated
from uuid import UUID

from pydantic import Field, ValidationError, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from fairmade.database import database_url, make_engine
from fairmade.models import Account, AccountRole, AdminBootstrapRecord, LoginSession
from fairmade.pricing.schemas import Contract


class BootstrapRequest(Contract):
    account_id: UUID
    reason: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("reason")
    @classmethod
    def no_null_characters(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Reason cannot contain null characters")
        return value


class BootstrapError(Exception):
    """Safe operator-facing refusal; never includes secrets or submitted reason."""


def provision(db: Session, body: BootstrapRequest) -> bool:
    target = str(body.account_id)
    db.execute(
        update(Account)
        .where(Account.id == target)
        .values(created_at=Account.created_at)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()
    if db.get(Account, target) is None:
        raise BootstrapError("The target account does not exist.")
    record = db.get(AdminBootstrapRecord, 1)
    existing_admin = db.scalar(select(AccountRole).where(AccountRole.role == "admin").limit(1))
    if record is not None:
        if record.account_id == target and db.get(AccountRole, (target, "admin")) is not None:
            db.commit()
            return False
        raise BootstrapError("Initial administrator bootstrap is already closed.")
    if existing_admin is not None:
        raise BootstrapError("Administrators already exist; initial bootstrap is closed.")
    db.add(AdminBootstrapRecord(id=1, account_id=target, reason=body.reason))
    db.add(AccountRole(account_id=target, role="admin"))
    # Previously issued low-privilege tokens must not become administrator tokens.
    db.execute(delete(LoginSession).where(LoginSession.account_id == target))
    db.commit()
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Provision the initial local administrator on an existing account."
    )
    parser.add_argument("--account-id", required=True)
    parser.add_argument(
        "--reason", required=True, help="Audit reason; do not include secrets or private documents."
    )
    args = parser.parse_args(argv)
    try:
        body = BootstrapRequest(account_id=args.account_id, reason=args.reason)
    except ValidationError:
        print("Invalid account ID or provisioning reason.", file=sys.stderr)
        return 2
    engine = None
    try:
        engine = make_engine(database_url())
        with Session(engine, expire_on_commit=False) as db:
            created = provision(db, body)
    except BootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (SQLAlchemyError, ValueError):
        print("Bootstrap failed; check database configuration and migrations.", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()
    print(
        "Initial administrator provisioned; sign in again."
        if created
        else "Initial administrator already provisioned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
