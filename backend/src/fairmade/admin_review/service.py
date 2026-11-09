"""One immutable manual decision; approval and additive seller access commit together."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from fairmade.admin_review import repository
from fairmade.admin_review.schemas import AdminApplication, DecisionRequest
from fairmade.auth import api_error
from fairmade.models import Account, AccountRole, SellerApplication, SellerApplicationDecision
from fairmade.schemas import SellerApplicationResponse


def error(status: int, code: str, message: str) -> HTTPException:
    result = api_error(status, code, message)
    result.headers = {"Cache-Control": "no-store"}
    return result


def require_application(db: Session, application_id: str) -> SellerApplication:
    application = repository.get(db, application_id)
    if application is None:
        raise error(404, "NOT_FOUND", "Resource not found.")
    return application


def admin_response(
    db: Session, application: SellerApplication, email: str | None = None
) -> AdminApplication:
    if email is None:
        email = db.get(Account, application.account_id).email
    return AdminApplication(
        **SellerApplicationResponse.model_validate(application).model_dump(),
        applicant_account_id=application.account_id,
        applicant_email=email,
        decided_by_account_id=application.decision.decided_by_account_id
        if application.decision
        else None,
    )


def decide(
    db: Session, admin_id: str, application_id: str, body: DecisionRequest
) -> SellerApplication:
    require_application(db, application_id)
    repository.reserve(db, application_id)
    if not repository.has_role(db, admin_id, "admin"):
        raise error(403, "ADMIN_REQUIRED", "Administrator access is required.")
    application = require_application(db, application_id)
    if application.account_id == admin_id:
        raise error(
            403, "SELF_REVIEW_FORBIDDEN", "An administrator cannot decide their own application."
        )
    existing = application.decision
    if existing is not None:
        if (
            existing.outcome == body.outcome
            and existing.reason == body.reason
            and existing.expected_revision == body.expected_revision
        ):
            # Never re-grant a role on a retry after access was revoked elsewhere.
            db.commit()
            return application
        raise error(
            409, "DECISION_ALREADY_RECORDED", "This application already has a final decision."
        )
    if application.revision != body.expected_revision:
        raise error(409, "REVISION_CONFLICT", "Application changed; reload before deciding.")
    if application.status != "pending":
        raise error(
            409, "APPLICATION_NOT_PENDING", "Only pending applications can receive a new decision."
        )
    if repository.has_role(db, application.account_id, "seller"):
        raise error(
            409,
            "SELLER_ALREADY_GRANTED",
            "The account already has seller access; no decision was recorded.",
        )
    decision = SellerApplicationDecision(
        application_id=application.id,
        decided_by_account_id=admin_id,
        outcome=body.outcome,
        reason=body.reason,
        expected_revision=body.expected_revision,
    )
    application.decision = decision
    application.status = body.outcome
    application.revision += 1
    if body.outcome == "approved":
        db.add(AccountRole(account_id=application.account_id, role="seller"))
    db.commit()
    return application
