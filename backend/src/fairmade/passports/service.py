"""Draft lifecycle, exact-preview approval, publication and withdrawal."""

from sqlalchemy import update
from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.models import PassportDraft, PassportPublication
from fairmade.passports import projection, repository
from fairmade.passports.errors import PassportError, conflict, missing
from fairmade.passports.schemas import DraftContent, Preview, PublishApproval, ReplaceDraft
from fairmade.reviews.schemas import ReviewResponse


def _source(db: Session, product_id: str, review_id: str) -> dict:
    review = repository.review_for_product(db, product_id, review_id)
    if review is None:
        raise missing()
    if review.review_version != "seller-pricing-review-v1":
        raise conflict("UNSUPPORTED_REVIEW_VERSION", "The selected review version is unsupported.")
    return ReviewResponse.model_validate(review).model_dump(mode="json")


def get_draft(db: Session, product_id: str, draft_id: str) -> PassportDraft:
    draft = repository.draft_for_product(db, product_id, draft_id)
    if draft is None:
        raise missing()
    return draft


def create_draft(db: Session, product_id: str, content: DraftContent) -> PassportDraft:
    _source(db, product_id, str(content.review_id))
    draft = PassportDraft(
        product_id=product_id, revision=1, content=content.model_dump(mode="json")
    )
    db.add(draft)
    db.commit()
    return draft


def replace_draft(
    db: Session,
    product_id: str,
    draft_id: str,
    replacement: ReplaceDraft,
) -> PassportDraft:
    get_draft(db, product_id, draft_id)
    content = DraftContent.model_validate(
        replacement.model_dump(mode="json", exclude={"expected_revision"}),
    )
    _source(db, product_id, str(content.review_id))
    changed = db.execute(
        update(PassportDraft)
        .where(
            PassportDraft.id == draft_id,
            PassportDraft.product_id == product_id,
            PassportDraft.revision == replacement.expected_revision,
        )
        .values(revision=replacement.expected_revision + 1, content=content.model_dump(mode="json"))
    )
    if changed.rowcount != 1:
        raise conflict()
    db.commit()
    db.expire_all()
    return get_draft(db, product_id, draft_id)


def preview(db: Session, product_id: str, draft_id: str) -> Preview:
    draft = get_draft(db, product_id, draft_id)
    content = DraftContent.model_validate(draft.content)
    source = _source(db, product_id, str(content.review_id))
    try:
        payload = projection.project(source, content)
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        raise PassportError(
            "UNSUPPORTED_REVIEW_VERSION",
            "The review cannot be projected using this Passport version.",
        ) from exc
    return Preview(
        draft_id=draft.id,
        revision=draft.revision,
        preview_hash=projection.digest(payload),
        payload=payload,
    )


def publish(
    db: Session,
    product_id: str,
    draft_id: str,
    approval: PublishApproval,
    approved_by_account_id: str,
) -> tuple[PassportPublication, bool]:
    get_draft(db, product_id, draft_id)
    if not repository.reserve_draft(db, product_id, draft_id, approval.expected_revision):
        raise conflict()
    checked = preview(db, product_id, draft_id)
    if checked.preview_hash != approval.preview_hash:
        raise conflict("PREVIEW_MISMATCH", "Approval must match the exact current preview.")
    existing = repository.publications_for_revision(db, draft_id, approval.expected_revision)
    if existing is not None:
        if existing.state != "published":
            raise conflict(
                "PUBLICATION_INACTIVE", "Edit the draft before publishing a new version."
            )
        db.commit()
        return existing, False
    repository.supersede_product_publications(db, product_id)
    publication = PassportPublication(
        product_id=product_id,
        draft_id=draft_id,
        draft_revision=checked.revision,
        approved_by_account_id=approved_by_account_id,
        state="published",
        payload_hash=checked.preview_hash,
        payload=projection.payload_dict(checked.payload),
    )
    db.add(publication)
    db.commit()
    return publication, True


def withdraw(db: Session, product_id: str, draft_id: str, publication_id: str) -> None:
    get_draft(db, product_id, draft_id)
    publication = repository.publication_for_draft(db, draft_id, publication_id)
    if publication is None:
        raise missing()
    db.execute(
        update(PassportPublication)
        .where(
            PassportPublication.id == publication_id,
            PassportPublication.state == "published",
        )
        .values(state="withdrawn", withdrawn_at=utcnow())
    )
    db.commit()


def get_publication(db: Session, publication_id: str) -> PassportPublication:
    publication = repository.visible_publication(db, publication_id)
    if publication is None:
        raise missing()
    return publication
