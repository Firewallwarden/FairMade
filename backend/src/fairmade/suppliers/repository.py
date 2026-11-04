"""Bounded, owner-scoped persistence for sourcing inputs and immutable evidence."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.models import Product, SourcingInput, SupplierComparison, SupplierQuote
from fairmade.ownership import require_owned_product


def require_input(
    db: Session,
    account_id: str,
    product_id: UUID,
    input_id: UUID,
) -> tuple[Product, SourcingInput]:
    product = require_owned_product(db, account_id, product_id)
    sourcing_input = db.scalar(
        select(SourcingInput).where(
            SourcingInput.id == str(input_id),
            SourcingInput.product_id == product.id,
        )
    )
    if sourcing_input is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return product, sourcing_input


def list_inputs(db: Session, product_id: str, limit: int, offset: int) -> list[SourcingInput]:
    return list(
        db.scalars(
            select(SourcingInput)
            .where(SourcingInput.product_id == product_id)
            .order_by(SourcingInput.created_at.desc(), SourcingInput.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def lock_revision(db: Session, sourcing_input: SourcingInput, revision: int) -> None:
    # Start the SQLite write transaction before loading rules. Replacements and
    # reports serialize; a stale editor cannot silently evaluate different rules.
    changed = db.execute(
        update(SourcingInput)
        .where(SourcingInput.id == sourcing_input.id, SourcingInput.rule_revision == revision)
        .values(rule_revision=revision, updated_at=SourcingInput.updated_at)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise api_error(
            409, "REVISION_CONFLICT", "Sourcing requirements changed; reload and retry."
        )
    db.refresh(sourcing_input)


def replace_rules(
    db: Session, sourcing_input: SourcingInput, revision: int, rules: list[dict]
) -> None:
    lock_revision(db, sourcing_input, revision)
    sourcing_input.rule_revision = revision + 1
    sourcing_input.rules = rules


def list_quotes(db: Session, input_id: str, limit: int, offset: int) -> list[SupplierQuote]:
    return list(
        db.scalars(
            select(SupplierQuote)
            .where(SupplierQuote.sourcing_input_id == input_id)
            .order_by(SupplierQuote.created_at.desc(), SupplierQuote.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def selected_quotes(db: Session, input_id: str, quote_ids: list[UUID]) -> list[SupplierQuote]:
    quotes = db.scalars(
        select(SupplierQuote).where(
            SupplierQuote.sourcing_input_id == input_id,
            SupplierQuote.id.in_([str(value) for value in quote_ids]),
        )
    ).all()
    if len(quotes) != len(quote_ids):
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    by_id = {quote.id: quote for quote in quotes}
    return [by_id[str(value)] for value in quote_ids]


def list_reports(db: Session, input_id: str, limit: int, offset: int) -> list[SupplierComparison]:
    return list(
        db.scalars(
            select(SupplierComparison)
            .where(SupplierComparison.sourcing_input_id == input_id)
            .order_by(SupplierComparison.created_at.desc(), SupplierComparison.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def require_report(db: Session, input_id: str, report_id: UUID) -> SupplierComparison:
    report = db.scalar(
        select(SupplierComparison).where(
            SupplierComparison.id == str(report_id),
            SupplierComparison.sourcing_input_id == input_id,
        )
    )
    if report is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return report
