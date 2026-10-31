"""Small in-memory interface for durable operation leases stored by repositories."""

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4


class LeaseRecord(Protocol):
    lease_token: str | None
    lease_expires_at: datetime | None


class LeaseBusy(Exception):
    pass


def claim_lease(record: LeaseRecord, now: datetime) -> str:
    deadline = record.lease_expires_at
    if deadline is not None:
        deadline = deadline.replace(tzinfo=UTC) if deadline.tzinfo is None else deadline
        if deadline > now:
            raise LeaseBusy()
    record.lease_token = str(uuid4())
    record.lease_expires_at = now + timedelta(seconds=60)
    return record.lease_token


def release_lease(record: LeaseRecord) -> None:
    record.lease_token = None
    record.lease_expires_at = None
