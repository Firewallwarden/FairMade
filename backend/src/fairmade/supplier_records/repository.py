"""Owner-scoped profiles, latest correction queries and exact integer summary inputs."""

from datetime import date

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session, aliased

from fairmade.models import (
    Product,
    SourcingInput,
    SupplierExperience,
    SupplierProfile,
    SupplierProfileEvent,
    SupplierQuote,
)


def owned(db: Session, account_id: str, supplier_id: str) -> SupplierProfile | None:
    return db.scalar(
        select(SupplierProfile).where(
            SupplierProfile.account_id == account_id, SupplierProfile.id == supplier_id
        )
    )


def profiles(
    db: Session, account_id: str, archived: bool | None, limit: int, offset: int
) -> list[SupplierProfile]:
    query = select(SupplierProfile).where(SupplierProfile.account_id == account_id)
    if archived is not None:
        query = query.where(SupplierProfile.archived == archived)
    return list(
        db.scalars(
            query.order_by(SupplierProfile.created_at.desc(), SupplierProfile.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def profile_retry(db: Session, account_id: str, request_id: str) -> SupplierProfileEvent | None:
    return db.scalar(
        select(SupplierProfileEvent).where(
            SupplierProfileEvent.account_id == account_id,
            SupplierProfileEvent.request_id == request_id,
        )
    )


def history(db: Session, supplier_id: str, limit: int, offset: int) -> list[SupplierProfileEvent]:
    return list(
        db.scalars(
            select(SupplierProfileEvent)
            .where(SupplierProfileEvent.supplier_id == supplier_id)
            .order_by(SupplierProfileEvent.revision.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def experience(db: Session, supplier_id: str, experience_id: str) -> SupplierExperience | None:
    return db.scalar(
        select(SupplierExperience).where(
            SupplierExperience.supplier_id == supplier_id, SupplierExperience.id == experience_id
        )
    )


def experience_retry(db: Session, supplier_id: str, request_id: str) -> SupplierExperience | None:
    return db.scalar(
        select(SupplierExperience).where(
            SupplierExperience.supplier_id == supplier_id,
            SupplierExperience.request_id == request_id,
        )
    )


def successor(db: Session, experience_id: str) -> str | None:
    return db.scalar(
        select(SupplierExperience.id).where(
            SupplierExperience.corrects_experience_id == experience_id
        )
    )


def owned_quote(db: Session, account_id: str, quote_id: str) -> SupplierQuote | None:
    return db.scalar(
        select(SupplierQuote)
        .join(SourcingInput, SourcingInput.id == SupplierQuote.sourcing_input_id)
        .join(Product, Product.id == SourcingInput.product_id)
        .where(Product.account_id == account_id, SupplierQuote.id == quote_id)
    )


def filtered(
    query: Select,
    supplier_id: str,
    since: date | None,
    until: date | None,
    include_corrected: bool = False,
) -> Select:
    record = SupplierExperience
    query = query.where(record.supplier_id == supplier_id)
    if not include_corrected:
        correction = aliased(SupplierExperience)
        query = query.where(
            ~select(correction.id).where(correction.corrects_experience_id == record.id).exists()
        )
    if since is not None:
        query = query.where(record.observed_on >= since)
    if until is not None:
        query = query.where(record.observed_on <= until)
    return query


def experiences(
    db: Session,
    supplier_id: str,
    since: date | None,
    until: date | None,
    include_corrected: bool,
    limit: int,
    offset: int,
) -> list[dict]:
    record = SupplierExperience
    query = select(
        record.id,
        record.supplier_id,
        record.request_id,
        record.supplier_revision,
        record.label,
        record.observed_on,
        record.rating,
        record.promised_on,
        record.received_on,
        record.source_quote_id,
        record.corrects_experience_id,
        record.created_at,
    )
    rows = db.execute(
        filtered(query, supplier_id, since, until, include_corrected)
        .order_by(record.observed_on.desc(), record.created_at.desc(), record.id.desc())
        .limit(limit)
        .offset(offset)
    ).mappings()
    return [dict(row) for row in rows]


def summary_inputs(db: Session, supplier_id: str, since: date | None, until: date | None) -> dict:
    record = SupplierExperience
    dated = record.promised_on.is_not(None) & record.received_on.is_not(None)
    on_time = dated & (record.received_on <= record.promised_on)
    # SQL AVG would introduce binary floats. Fetch integer sums/counts only.
    query = select(
        func.count().label("total"),
        func.count(record.rating).label("rated"),
        func.coalesce(func.sum(record.rating), 0).label("rating_sum"),
        func.coalesce(func.sum(case((dated, 1), else_=0)), 0).label("dated"),
        func.coalesce(func.sum(case((on_time, 1), else_=0)), 0).label("on_time"),
    ).select_from(record)
    return dict(db.execute(filtered(query, supplier_id, since, until)).mappings().one())
