"""Retry-safe private observations; ratings never certify supplier or ingredient quality."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.models import SupplierExperience, SupplierProfile, SupplierProfileEvent
from fairmade.ownership import reserve_seller_account
from fairmade.supplier_records import repository
from fairmade.supplier_records.schemas import (
    ExperienceRequest,
    ProfileCreate,
    ProfileReplacement,
    ProfileResponse,
    ReliabilityResponse,
)
from fairmade.suppliers.schemas import SupplierQuoteResponse


def error(status: int, code: str, message: str) -> HTTPException:
    exception = api_error(status, code, message)
    exception.headers = {"Cache-Control": "no-store"}
    return exception


def require_profile(db: Session, account_id: str, supplier_id: str) -> SupplierProfile:
    profile = repository.owned(db, account_id, supplier_id)
    if profile is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return profile


def require_experience(db: Session, supplier_id: str, experience_id: str) -> SupplierExperience:
    record = repository.experience(db, supplier_id, experience_id)
    if record is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return record


def check_revision(actual: int, expected: int) -> None:
    if actual != expected:
        raise error(409, "REVISION_CONFLICT", "Supplier metadata changed; reload before recording.")


def validate_window(since: date | None, until: date | None) -> None:
    if since is not None and until is not None and since > until:
        raise error(422, "INVALID_DATE_RANGE", "Observation date range must be ordered.")


def save_profile(
    db: Session,
    account_id: str,
    body: ProfileCreate | ProfileReplacement,
    supplier_id: str | None = None,
) -> tuple[SupplierProfileEvent, bool]:
    if supplier_id is not None:
        require_profile(db, account_id, supplier_id)
    reserve_seller_account(db, account_id)
    previous = repository.profile_retry(db, account_id, str(body.request_id))
    if previous is not None:
        if (supplier_id is not None and supplier_id != previous.supplier_id) or (
            previous.request != body.model_dump(mode="json")
        ):
            raise error(409, "IDEMPOTENCY_CONFLICT", "This request ID was used for another change.")
        db.commit()
        return previous, False
    now = utcnow()
    before = None
    if supplier_id is None:
        profile = SupplierProfile(account_id=account_id, revision=1, created_at=now, updated_at=now)
        reason = "Initial supplier registration."
    else:
        profile = require_profile(db, account_id, supplier_id)
        check_revision(profile.revision, body.expected_revision)
        before = ProfileResponse.model_validate(profile).model_dump(mode="json")
        profile.revision += 1
        reason = body.reason
    existing = db.scalar(
        select(SupplierProfile.id).where(
            SupplierProfile.account_id == account_id,
            SupplierProfile.name_key == body.name.casefold(),
        )
    )
    if existing is not None and existing != profile.id:
        raise error(409, "SUPPLIER_EXISTS", "A supplier with this name already exists.")
    profile.name = body.name
    profile.name_key = body.name.casefold()
    profile.location = body.location
    profile.notes = body.notes
    profile.archived = int(body.archived)
    profile.updated_at = now
    db.add(profile)
    db.flush()
    event = SupplierProfileEvent(
        account_id=account_id,
        supplier_id=profile.id,
        request_id=str(body.request_id),
        revision=profile.revision,
        reason=reason,
        before=before,
        after=ProfileResponse.model_validate(profile).model_dump(mode="json"),
        request=body.model_dump(mode="json"),
    )
    db.add(event)
    db.commit()
    return event, True


def save_experience(
    db: Session,
    account_id: str,
    supplier_id: str,
    body: ExperienceRequest,
) -> tuple[SupplierExperience, bool]:
    require_profile(db, account_id, supplier_id)
    reserve_seller_account(db, account_id)
    profile = require_profile(db, account_id, supplier_id)
    previous = repository.experience_retry(db, supplier_id, str(body.request_id))
    if previous is not None:
        if ExperienceRequest.model_validate(previous.request) != body:
            raise error(
                409, "IDEMPOTENCY_CONFLICT", "This request ID was used for another experience."
            )
        db.commit()
        return previous, False
    corrects_id = str(body.corrects_experience_id) if body.corrects_experience_id else None
    prior = None
    if corrects_id is not None:
        prior = require_experience(db, supplier_id, corrects_id)
        if repository.successor(db, prior.id) is not None:
            raise error(
                409,
                "EXPERIENCE_ALREADY_CORRECTED",
                "Correct the latest experience in this history.",
            )
        check_revision(prior.supplier_revision, body.expected_supplier_revision)
        snapshot = prior.supplier_snapshot
    else:
        check_revision(profile.revision, body.expected_supplier_revision)
        snapshot = ProfileResponse.model_validate(profile).model_dump(mode="json")
    quote_id = str(body.source_quote_id) if body.source_quote_id else None
    quote_snapshot = None
    if prior is not None and prior.source_quote_id == quote_id:
        quote_snapshot = prior.quote_snapshot
    elif quote_id is not None:
        quote = repository.owned_quote(db, account_id, quote_id)
        if quote is None:
            raise error(404, "NOT_FOUND", "Resource not found.")
        quote_snapshot = SupplierQuoteResponse.model_validate(quote).model_dump(mode="json")
    record = SupplierExperience(
        supplier_id=supplier_id,
        request_id=str(body.request_id),
        supplier_revision=body.expected_supplier_revision,
        label=body.label,
        observed_on=body.observed_on,
        rating=body.rating,
        promised_on=body.promised_on,
        received_on=body.received_on,
        source_quote_id=quote_id,
        corrects_experience_id=corrects_id,
        supplier_snapshot=snapshot,
        quote_snapshot=quote_snapshot,
        request=body.model_dump(mode="json"),
    )
    db.add(record)
    db.commit()
    return record, True


def ratio(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 60
        return (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )


def reliability(
    db: Session,
    supplier_id: str,
    since: date | None,
    until: date | None,
) -> ReliabilityResponse:
    values = repository.summary_inputs(db, supplier_id, since, until)
    return ReliabilityResponse(
        supplier_id=supplier_id,
        observed_from=since,
        observed_until=until,
        experiences_count=values["total"],
        rated_count=values["rated"],
        average_rating=ratio(values["rating_sum"], values["rated"]),
        dated_deliveries_count=values["dated"],
        on_time_count=values["on_time"],
        late_count=values["dated"] - values["on_time"],
        unknown_delivery_count=values["total"] - values["dated"],
        on_time_fraction=ratio(values["on_time"], values["dated"]),
        notices=[
            "Private seller reports; not verified performance or a representative sample.",
            "Ratings are opinions. Missing delivery dates stay unknown; experiences may overlap.",
            "Ratings do not override mandatory Quality Locks or verify quote availability.",
        ],
    )
