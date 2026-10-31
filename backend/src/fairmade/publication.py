"""Shared exact-preview approval and canonical public-payload hashing."""

import hashlib
import json
from typing import Annotated, Self

from pydantic import BaseModel, Field, StrictBool, model_validator

from fairmade.pricing.schemas import Contract

Revision = Annotated[int, Field(strict=True, ge=1, le=2_147_483_646)]


class PublishApproval(Contract):
    expected_revision: Revision
    preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    approved: StrictBool

    @model_validator(mode="after")
    def explicit_approval(self) -> Self:
        if not self.approved:
            raise ValueError("Publication requires explicit approval")
        return self


def public_digest(payload: BaseModel) -> str:
    encoded = json.dumps(
        payload.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
