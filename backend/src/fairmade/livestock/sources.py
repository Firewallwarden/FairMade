"""Explicit production attribution; profiles are frozen at recording, not inferred historically."""

from sqlalchemy.orm import Session

from fairmade.database import utcnow
from fairmade.livestock.schemas import AnimalResponse, GroupProfile, LivestockReference
from fairmade.livestock.service import check_revision, require_animal, require_group
from fairmade.models import ProductionLivestockSource, ProductionRecord


def attach(
    db: Session,
    account_id: str,
    record: ProductionRecord,
    reference: LivestockReference | None,
    prior: ProductionRecord | None,
) -> None:
    if reference is None:
        return
    # Full corrections that retain the same reference preserve its historical
    # snapshot, even after the source profile or current membership has changed.
    if prior is not None and prior.request.get("livestock_source") == reference.model_dump(
        mode="json"
    ):
        original = prior.livestock_attribution
        if original is not None:
            record.livestock_attribution = ProductionLivestockSource(
                group_id=original.group_id,
                animal_id=original.animal_id,
                snapshot=original.snapshot,
            )
            return
    group = None
    animal = None
    if reference.kind == "group":
        group = require_group(db, account_id, str(reference.id))
        check_revision(group.revision, reference.expected_revision)
    else:
        animal = require_animal(db, account_id, str(reference.id))
        check_revision(animal.revision, reference.expected_revision)
        if animal.group_id is not None:
            group = require_group(db, account_id, animal.group_id)
    snapshot = {
        "kind": reference.kind,
        "group": GroupProfile.model_validate(group).model_dump(mode="json") if group else None,
        "animal": AnimalResponse.model_validate(animal).model_dump(mode="json") if animal else None,
        "recorded_at": utcnow().isoformat(),
        "basis": "seller_reported_unverified",
        "notice": (
            "Profiles at recording time; not proof of historical membership or per-animal yield."
        ),
    }
    record.livestock_attribution = ProductionLivestockSource(
        group_id=group.id if group else None,
        animal_id=animal.id if animal else None,
        snapshot=snapshot,
    )
