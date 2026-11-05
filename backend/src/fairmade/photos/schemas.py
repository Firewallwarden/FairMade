"""Photo selections and allowlisted metadata; original files are never returned."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fairmade.pricing.schemas import Contract, Label
from fairmade.schemas import UTCResponse


class PhotoSelection(Contract):
    photo_id: UUID
    alt_text: Label


class PhotoMetadata(UTCResponse):
    id: UUID
    product_id: UUID
    created_at: datetime
    width: int
    height: int
    byte_count: int
    sha256: str
    media_type: Literal["image/jpeg"] = "image/jpeg"


class PublicPhoto(Contract):
    id: UUID
    src: str
    alt_text: str
    width: int
    height: int
    sha256: str
    media_type: Literal["image/jpeg"] = "image/jpeg"
