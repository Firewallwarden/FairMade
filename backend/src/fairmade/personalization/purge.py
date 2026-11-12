"""Erase expired preference data while preserving minimal revision tombstones."""

from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.database import database_url, make_engine, utcnow
from fairmade.models import BuyerProfile
from fairmade.personalization.erasure import erase_answers
from fairmade.personalization.profiles import reserve


def purge(db: Session) -> int:
    identifiers = db.scalars(
        select(BuyerProfile.account_id)
        .where(BuyerProfile.enabled == 1, BuyerProfile.expires_at <= utcnow())
        .order_by(BuyerProfile.account_id)
        .limit(100)
    ).all()
    count = 0
    for account_id in identifiers:
        reserve(db, account_id)
        row = db.get(BuyerProfile, account_id)
        if not row.enabled or row.expires_at.replace(tzinfo=UTC) > utcnow():
            continue
        erase_answers(db, account_id)
        row.enabled, row.preferences, row.expires_at = False, {}, None
        row.revision = min(2147483646, row.revision + 1)
        row.updated_at = utcnow()
        count += 1
    return count


def main():
    engine = make_engine(database_url())
    try:
        with Session(engine) as db:
            count = purge(db)
            db.commit()
        print(f"Cleared {count} expired buyer preference profiles.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
