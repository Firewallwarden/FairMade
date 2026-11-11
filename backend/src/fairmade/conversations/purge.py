"""Operator cleanup: remove expired conversations and cascaded turns from the configured DB."""

from sqlalchemy.orm import Session

from fairmade.conversations.repository import purge_expired
from fairmade.database import database_url, make_engine


def main():
    engine = make_engine(database_url())
    try:
        with Session(engine) as db:
            count = purge_expired(db)
            db.commit()
        print(f"Purged {count} expired assistant conversations.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
