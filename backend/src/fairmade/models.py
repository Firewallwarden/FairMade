"""General accounts, additive roles, and private seller data."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fairmade.database import Base, utcnow


def new_id() -> str:
    return str(uuid4())


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    role_grants: Mapped[list["AccountRole"]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def roles(self) -> list[str]:
        granted = {grant.role for grant in self.role_grants}
        return [role for role in ("buyer", "seller", "admin") if role in granted]


class AccountRole(Base):
    __tablename__ = "account_roles"
    __table_args__ = (
        CheckConstraint("role IN ('buyer', 'seller', 'admin')", name="ck_account_roles_role"),
    )
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(6), primary_key=True)


class SellerApplication(Base):
    __tablename__ = "seller_applications"
    __table_args__ = (CheckConstraint("status = 'pending'", name="ck_seller_applications_status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), unique=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(7), default="pending", server_default="pending")


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    product_type: Mapped[str] = mapped_column(String(20))
    selling_unit: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    calculation_version: Mapped[str] = mapped_column(String(100))
    product_snapshot: Mapped[dict] = mapped_column(JSON)
    inputs: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class QualityLockSet(Base):
    __tablename__ = "quality_lock_sets"
    __table_args__ = (CheckConstraint("revision >= 0", name="ck_quality_lock_sets_revision"),)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    rules: Mapped[list] = mapped_column(JSON)


class QualityEvaluation(Base):
    __tablename__ = "quality_evaluations"
    __table_args__ = (
        CheckConstraint("rule_revision >= 0", name="ck_quality_evaluations_revision"),
        CheckConstraint(
            "status IN ('passed', 'failed', 'unknown', 'not_evaluated')",
            name="ck_quality_evaluations_status",
        ),
        CheckConstraint(
            "basis = 'seller_reported_unverified'",
            name="ck_quality_evaluations_basis",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    candidate_label: Mapped[str] = mapped_column(String(200))
    rule_revision: Mapped[int] = mapped_column(Integer)
    evaluation_version: Mapped[str] = mapped_column(String(100))
    basis: Mapped[str] = mapped_column(String(40))
    rules_snapshot: Mapped[list] = mapped_column(JSON)
    claims: Mapped[dict] = mapped_column(JSON)
    checks: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        CheckConstraint(
            "basis = 'seller_reported_unverified'",
            name="ck_price_observations_basis",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    basis: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)


class PriceComparison(Base):
    __tablename__ = "price_comparisons"
    __table_args__ = (
        CheckConstraint(
            "basis = 'seller_reported_unverified'",
            name="ck_price_comparisons_basis",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    as_of_date: Mapped[date] = mapped_column(Date)
    comparison_version: Mapped[str] = mapped_column(String(100))
    basis: Mapped[str] = mapped_column(String(40))
    request_snapshot: Mapped[dict] = mapped_column(JSON)
    product_snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
