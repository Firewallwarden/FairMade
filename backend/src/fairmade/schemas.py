"""Account and private product/history wire models."""

from datetime import UTC, datetime
from typing import Annotated, Generic, Literal, Self, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

from fairmade.pricing.schemas import Contract, Label

ProductType = Literal["sourdough", "eggs", "other"]
Description = Annotated[str, Field(max_length=2000)]


class Credentials(BaseModel):
    # Do not inherit whitespace stripping: passwords must be used verbatim.
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.casefold()


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    roles: list[Literal["buyer", "seller", "admin"]]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime


class ProductCreate(Contract):
    name: Label
    product_type: ProductType
    selling_unit: Label
    description: Description | None = None


class ProductUpdate(Contract):
    name: Label | SkipJsonSchema[None] = None
    product_type: ProductType | SkipJsonSchema[None] = None
    selling_unit: Label | SkipJsonSchema[None] = None
    description: Description | None = None

    @model_validator(mode="after")
    def required_fields_cannot_be_null(self) -> Self:
        for name in ("name", "product_type", "selling_unit"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class UTCResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", "updated_at", "submitted_at", check_fields=False)
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        # SQLite stores UTC timestamps without timezone information.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SellerApplicationRequest(Contract):
    """An application records intent only; verification fields are not accepted."""


class SellerApplicationResponse(UTCResponse):
    id: UUID
    status: Literal["pending"]
    submitted_at: datetime


class ProductResponse(UTCResponse):
    id: UUID
    name: str
    product_type: ProductType
    selling_unit: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class AnalysisSummary(UTCResponse):
    id: UUID
    created_at: datetime
    calculation_version: str


class AnalysisResponse(AnalysisSummary):
    product_id: UUID
    product_snapshot: ProductResponse
    # Historical JSON is returned verbatim, independent of future calculator schemas.
    inputs: dict
    result: dict


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail
