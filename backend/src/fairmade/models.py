"""General accounts, additive roles, and private seller data."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fairmade.database import Base, utcnow


def new_id() -> str:
    return str(uuid4())


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"
    __table_args__ = (
        Index("ix_buyer_profile_expiry", "expires_at"),
        CheckConstraint("revision BETWEEN 1 AND 2147483646", name="ck_buyer_profile_revision"),
        CheckConstraint(
            "(enabled = 1 AND expires_at IS NOT NULL) OR (enabled = 0 AND expires_at IS NULL)",
            name="ck_buyer_profile_expiry",
        ),
    )
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Integer)
    preferences: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ReceiptDraft(Base):
    __tablename__ = "receipt_drafts"
    __table_args__ = (
        UniqueConstraint("account_id", "request_id", name="uq_receipt_request"),
        UniqueConstraint("account_id", "source_hash", name="uq_receipt_image"),
        CheckConstraint("revision BETWEEN 1 AND 2147483646", name="ck_receipt_revision"),
        CheckConstraint("state IN ('draft', 'approved')", name="ck_receipt_state"),
        CheckConstraint(
            "(state = 'draft' AND approved_at IS NULL) OR "
            "(state = 'approved' AND approved_at IS NOT NULL)",
            name="ck_receipt_approval",
        ),
        Index("ix_receipt_owner_created", "account_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    source_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(12))
    ocr_text: Mapped[str] = mapped_column(Text)
    provenance: Mapped[dict] = mapped_column(JSON)
    extracted: Mapped[dict] = mapped_column(JSON)
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)


class ReceiptExpense(Base):
    __tablename__ = "receipt_expenses"
    __table_args__ = (Index("ix_receipt_expense_owner_created", "account_id", "created_at", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    receipt_id: Mapped[str] = mapped_column(ForeignKey("receipt_drafts.id"), unique=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"
    __table_args__ = (
        UniqueConstraint("account_id", "request_id", name="uq_conversation_request"),
        CheckConstraint("role IN ('buyer', 'seller')", name="ck_conversation_role"),
        CheckConstraint("revision BETWEEN 0 AND 40", name="ck_conversation_revision"),
        Index("ix_conversation_owner_updated", "account_id", "updated_at", "id"),
        Index("ix_conversation_expiry", "expires_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(6))
    scope: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AssistantTurn(Base):
    __tablename__ = "assistant_turns"
    __table_args__ = (
        UniqueConstraint("conversation_id", "request_id", name="uq_conversation_turn_request"),
        UniqueConstraint("conversation_id", "revision", name="uq_conversation_turn_revision"),
        CheckConstraint("revision BETWEEN 1 AND 40", name="ck_conversation_turn_revision"),
        CheckConstraint("length(question) BETWEEN 1 AND 2000", name="ck_conversation_question"),
        CheckConstraint("context_turns BETWEEN 0 AND 6", name="ck_conversation_context_turns"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("assistant_conversations.id", ondelete="CASCADE")
    )
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    response: Mapped[dict] = mapped_column(JSON)
    source_hash: Mapped[str] = mapped_column(String(64))
    history_period: Mapped[dict | None] = mapped_column(JSON)
    proposed_prices: Mapped[list] = mapped_column(JSON)
    context_turns: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DescriptionDraft(Base):
    __tablename__ = "description_drafts"
    __table_args__ = (
        UniqueConstraint("product_id", "request_id", name="uq_description_draft_request"),
        CheckConstraint("revision BETWEEN 1 AND 2147483646", name="ck_description_draft_revision"),
        CheckConstraint("state IN ('draft', 'approved')", name="ck_description_draft_state"),
        CheckConstraint("length(description) BETWEEN 1 AND 2000", name="ck_description_draft_text"),
        CheckConstraint(
            "provider = 'ollama_local' AND model = 'qwen3:8b'", name="ck_description_draft_provider"
        ),
        CheckConstraint("tone IN ('plain', 'friendly')", name="ck_description_draft_tone"),
        CheckConstraint(
            "(state = 'draft' AND approved_at IS NULL AND approved_by_account_id IS NULL) OR "
            "(state = 'approved' AND approved_at IS NOT NULL "
            "AND approved_by_account_id IS NOT NULL)",
            name="ck_description_draft_approval",
        ),
        Index("ix_description_draft_product_created", "product_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(12))
    generated_text: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    source_snapshot: Mapped[dict] = mapped_column(JSON)
    source_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(40))
    tone: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    role_grants: Mapped[list[AccountRole]] = relationship(
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
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'denied')", name="ck_seller_applications_status"
        ),
        CheckConstraint("revision >= 1", name="ck_seller_applications_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), unique=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(8), default="pending", server_default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    decision: Mapped[SellerApplicationDecision | None] = relationship(uselist=False)


class SellerApplicationDecision(Base):
    __tablename__ = "seller_application_decisions"
    __table_args__ = (
        CheckConstraint("outcome IN ('approved', 'denied')", name="ck_seller_decision_outcome"),
        CheckConstraint("expected_revision >= 1", name="ck_seller_decision_revision"),
        CheckConstraint("length(reason) BETWEEN 1 AND 2000", name="ck_seller_decision_reason"),
    )
    application_id: Mapped[str] = mapped_column(
        ForeignKey("seller_applications.id"), primary_key=True
    )
    decided_by_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    outcome: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str] = mapped_column(Text)
    expected_revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AdminBootstrapRecord(Base):
    __tablename__ = "admin_bootstrap_records"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_admin_bootstrap_singleton"),
        CheckConstraint("length(reason) BETWEEN 1 AND 2000", name="ck_admin_bootstrap_reason"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


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


class ProductRecipe(Base):
    __tablename__ = "product_recipes"
    __table_args__ = (CheckConstraint("revision >= 1", name="ck_product_recipe_revision"),)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RecipeCosting(Base):
    __tablename__ = "recipe_costings"
    __table_args__ = (
        UniqueConstraint("product_id", "request_id", name="uq_recipe_costing_request"),
        CheckConstraint("recipe_revision >= 1", name="ck_recipe_costing_revision"),
        Index("ix_recipe_costings_product_created", "product_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("product_recipes.product_id"))
    request_id: Mapped[str] = mapped_column(String(36))
    recipe_revision: Mapped[int] = mapped_column(Integer)
    pricing_analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), unique=True)
    recipe_snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (
        UniqueConstraint("account_id", "name_key", name="uq_material_account_name"),
        CheckConstraint("revision >= 1", name="ck_material_revision"),
        CheckConstraint("unit IN ('g', 'ml', 'item')", name="ck_material_unit"),
        CheckConstraint(
            "on_hand_micros BETWEEN 0 AND 1000000000000000", name="ck_material_balance"
        ),
        CheckConstraint(
            "unit != 'item' OR on_hand_micros % 1000000 = 0", name="ck_material_whole_items"
        ),
        Index("ix_materials_account_created", "account_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(600))
    notes: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(4))
    on_hand_micros: Mapped[int] = mapped_column(BigInteger)
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MaterialMovement(Base):
    __tablename__ = "material_movements"
    __table_args__ = (
        UniqueConstraint("material_id", "request_id", name="uq_material_movement_request"),
        UniqueConstraint("material_id", "revision", name="uq_material_movement_revision"),
        CheckConstraint("revision >= 2", name="ck_material_movement_revision"),
        CheckConstraint(
            "kind IN ('receipt', 'usage', 'waste', 'adjustment')", name="ck_material_movement_kind"
        ),
        CheckConstraint("unit IN ('g', 'ml', 'item')", name="ck_material_movement_unit"),
        CheckConstraint(
            "before_micros BETWEEN 0 AND 1000000000000000 "
            "AND after_micros BETWEEN 0 AND 1000000000000000",
            name="ck_material_movement_balance",
        ),
        CheckConstraint(
            "unit != 'item' OR (before_micros % 1000000 = 0 AND after_micros % 1000000 = 0)",
            name="ck_material_movement_whole_items",
        ),
        CheckConstraint(
            "(kind = 'receipt' AND after_micros > before_micros) OR "
            "(kind IN ('usage', 'waste') AND after_micros < before_micros) OR kind = 'adjustment'",
            name="ck_material_movement_direction",
        ),
        Index("ix_material_movements_material_revision", "material_id", "revision", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    material_name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(4))
    before_micros: Mapped[int] = mapped_column(BigInteger)
    after_micros: Mapped[int] = mapped_column(BigInteger)
    request: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ProductionRecord(Base):
    __tablename__ = "production_records"
    __table_args__ = (
        UniqueConstraint("product_id", "request_id", name="uq_production_record_request"),
        UniqueConstraint("corrects_record_id", name="uq_production_record_correction"),
        CheckConstraint("kind IN ('batch', 'production_period')", name="ck_production_record_kind"),
        CheckConstraint(
            "total_units BETWEEN 0 AND 1000000 AND sellable_units BETWEEN 0 AND total_units",
            name="ck_production_record_output",
        ),
        CheckConstraint("started_on <= completed_on", name="ck_production_record_dates"),
        Index(
            "ix_production_record_product_completed",
            "product_id",
            "completed_on",
            "created_at",
            "id",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    label: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(17))
    started_on: Mapped[date] = mapped_column(Date)
    completed_on: Mapped[date] = mapped_column(Date)
    selling_unit: Mapped[str] = mapped_column(String(200))
    total_units: Mapped[int] = mapped_column(Integer)
    sellable_units: Mapped[int] = mapped_column(Integer)
    corrects_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("production_records.id"), nullable=True
    )
    product_snapshot: Mapped[dict] = mapped_column(JSON)
    request: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    livestock_attribution: Mapped[ProductionLivestockSource | None] = relationship(uselist=False)

    @property
    def livestock_snapshot(self) -> dict | None:
        return self.livestock_attribution.snapshot if self.livestock_attribution else None


class LivestockGroup(Base):
    __tablename__ = "livestock_groups"
    __table_args__ = (
        UniqueConstraint("account_id", "name_key", name="uq_livestock_group_name"),
        CheckConstraint("revision >= 1", name="ck_livestock_group_revision"),
        CheckConstraint("archived IN (0, 1)", name="ck_livestock_group_archived"),
        CheckConstraint(
            "(reported_headcount IS NULL AND headcount_on IS NULL) OR "
            "(reported_headcount IS NOT NULL AND reported_headcount BETWEEN 0 AND 1000000 "
            "AND headcount_on IS NOT NULL)",
            name="ck_livestock_group_headcount",
        ),
        Index("ix_livestock_groups_account_created", "account_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(600))
    species: Mapped[str] = mapped_column(String(200))
    species_key: Mapped[str] = mapped_column(String(600))
    breed: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    reported_headcount: Mapped[int | None] = mapped_column(Integer)
    headcount_on: Mapped[date | None] = mapped_column(Date)
    archived: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LivestockAnimal(Base):
    __tablename__ = "livestock_animals"
    __table_args__ = (
        UniqueConstraint("account_id", "identifier_key", name="uq_livestock_animal_identifier"),
        CheckConstraint("revision >= 1", name="ck_livestock_animal_revision"),
        CheckConstraint("sex IN ('unknown', 'female', 'male')", name="ck_livestock_animal_sex"),
        CheckConstraint(
            "status IN ('active', 'departed', 'deceased')", name="ck_livestock_animal_status"
        ),
        CheckConstraint(
            "status = 'active' OR group_id IS NULL", name="ck_livestock_animal_membership"
        ),
        CheckConstraint(
            "born_on IS NULL OR acquired_on IS NULL OR born_on <= acquired_on",
            name="ck_livestock_animal_dates",
        ),
        Index("ix_livestock_animals_account_created", "account_id", "created_at", "id"),
        Index("ix_livestock_animals_group_status", "group_id", "status", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    identifier: Mapped[str] = mapped_column(String(200))
    identifier_key: Mapped[str] = mapped_column(String(600))
    name: Mapped[str | None] = mapped_column(String(200))
    species: Mapped[str] = mapped_column(String(200))
    species_key: Mapped[str] = mapped_column(String(600))
    breed: Mapped[str | None] = mapped_column(String(200))
    sex: Mapped[str] = mapped_column(String(7))
    born_on: Mapped[date | None] = mapped_column(Date)
    acquired_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(8))
    group_id: Mapped[str | None] = mapped_column(ForeignKey("livestock_groups.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LivestockGroupEvent(Base):
    __tablename__ = "livestock_group_events"
    __table_args__ = (
        UniqueConstraint("account_id", "request_id", name="uq_livestock_group_event_request"),
        UniqueConstraint("group_id", "revision", name="uq_livestock_group_event_revision"),
        CheckConstraint("revision >= 1", name="ck_livestock_group_event_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    group_id: Mapped[str] = mapped_column(ForeignKey("livestock_groups.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    occurred_on: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    request: Mapped[dict] = mapped_column(JSON)
    before: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    after: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LivestockAnimalEvent(Base):
    __tablename__ = "livestock_animal_events"
    __table_args__ = (
        UniqueConstraint("account_id", "request_id", name="uq_livestock_animal_event_request"),
        UniqueConstraint("animal_id", "revision", name="uq_livestock_animal_event_revision"),
        CheckConstraint("revision >= 1", name="ck_livestock_animal_event_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    animal_id: Mapped[str] = mapped_column(ForeignKey("livestock_animals.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    occurred_on: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    request: Mapped[dict] = mapped_column(JSON)
    before: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    after: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ProductionLivestockSource(Base):
    __tablename__ = "production_livestock_sources"
    __table_args__ = (
        CheckConstraint(
            "group_id IS NOT NULL OR animal_id IS NOT NULL", name="ck_production_livestock_target"
        ),
        Index("ix_production_livestock_group", "group_id", "record_id"),
        Index("ix_production_livestock_animal", "animal_id", "record_id"),
    )
    record_id: Mapped[str] = mapped_column(ForeignKey("production_records.id"), primary_key=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("livestock_groups.id"))
    animal_id: Mapped[str | None] = mapped_column(ForeignKey("livestock_animals.id"))
    snapshot: Mapped[dict] = mapped_column(JSON)


class ProductSalesCostBasis(Base):
    __tablename__ = "product_sales_cost_bases"
    __table_args__ = (
        CheckConstraint("revision >= 0", name="ck_product_sales_cost_basis_revision"),
        CheckConstraint(
            "(analysis_id IS NULL AND source_snapshot IS NULL) OR "
            "(analysis_id IS NOT NULL AND source_snapshot IS NOT NULL)",
            name="ck_product_sales_cost_basis_source",
        ),
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    analysis_id: Mapped[str | None] = mapped_column(ForeignKey("analyses.id"), nullable=True)
    source_snapshot: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)


class OrderSalesCostSnapshot(Base):
    __tablename__ = "order_sales_cost_snapshots"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'unavailable')", name="ck_order_sales_cost_snapshot_status"
        ),
        CheckConstraint(
            "(status = 'available' AND estimated_cost IS NOT NULL) OR "
            "(status = 'unavailable' AND estimated_cost IS NULL)",
            name="ck_order_sales_cost_snapshot_cost",
        ),
    )
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(20))
    # Decimal strings avoid SQLite float conversion and integer range overflow.
    estimated_cost: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSON)


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


class SourcingInput(Base):
    __tablename__ = "sourcing_inputs"
    __table_args__ = (
        CheckConstraint("rule_revision >= 0", name="ck_sourcing_inputs_revision"),
        Index("ix_sourcing_input_product_created", "product_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    label: Mapped[str] = mapped_column(String(200))
    rule_revision: Mapped[int] = mapped_column(Integer, default=0)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SupplierQuote(Base):
    __tablename__ = "supplier_quotes"
    __table_args__ = (
        CheckConstraint("basis = 'seller_reported_unverified'", name="ck_supplier_quotes_basis"),
        Index("ix_supplier_quote_input_created", "sourcing_input_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sourcing_input_id: Mapped[str] = mapped_column(ForeignKey("sourcing_inputs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    basis: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)


class SupplierProfile(Base):
    __tablename__ = "supplier_profiles"
    __table_args__ = (
        UniqueConstraint("account_id", "name_key", name="uq_supplier_profile_name"),
        CheckConstraint("revision >= 1", name="ck_supplier_profile_revision"),
        CheckConstraint("archived IN (0, 1)", name="ck_supplier_profile_archived"),
        Index("ix_supplier_profiles_account_created", "account_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(600))
    location: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    archived: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SupplierProfileEvent(Base):
    __tablename__ = "supplier_profile_events"
    __table_args__ = (
        UniqueConstraint("account_id", "request_id", name="uq_supplier_profile_event_request"),
        UniqueConstraint("supplier_id", "revision", name="uq_supplier_profile_event_revision"),
        CheckConstraint("revision >= 1", name="ck_supplier_profile_event_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("supplier_profiles.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    request: Mapped[dict] = mapped_column(JSON)
    before: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    after: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SupplierExperience(Base):
    __tablename__ = "supplier_experiences"
    __table_args__ = (
        UniqueConstraint("supplier_id", "request_id", name="uq_supplier_experience_request"),
        UniqueConstraint("corrects_experience_id", name="uq_supplier_experience_correction"),
        CheckConstraint("supplier_revision >= 1", name="ck_supplier_experience_revision"),
        CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_supplier_experience_rating"
        ),
        CheckConstraint(
            "received_on IS NULL OR received_on <= observed_on", name="ck_supplier_experience_dates"
        ),
        CheckConstraint(
            "(source_quote_id IS NULL AND quote_snapshot IS NULL) OR "
            "(source_quote_id IS NOT NULL AND quote_snapshot IS NOT NULL)",
            name="ck_supplier_experience_quote",
        ),
        Index("ix_supplier_experiences_observed", "supplier_id", "observed_on", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("supplier_profiles.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    supplier_revision: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(200))
    observed_on: Mapped[date] = mapped_column(Date)
    rating: Mapped[int | None] = mapped_column(Integer)
    promised_on: Mapped[date | None] = mapped_column(Date)
    received_on: Mapped[date | None] = mapped_column(Date)
    source_quote_id: Mapped[str | None] = mapped_column(ForeignKey("supplier_quotes.id"))
    corrects_experience_id: Mapped[str | None] = mapped_column(
        ForeignKey("supplier_experiences.id")
    )
    supplier_snapshot: Mapped[dict] = mapped_column(JSON)
    quote_snapshot: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    request: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SupplierComparison(Base):
    __tablename__ = "supplier_comparisons"
    __table_args__ = (
        CheckConstraint(
            "basis = 'seller_reported_unverified'", name="ck_supplier_comparisons_basis"
        ),
        CheckConstraint("rule_revision >= 0", name="ck_supplier_comparisons_revision"),
        Index("ix_supplier_comparison_input_created", "sourcing_input_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sourcing_input_id: Mapped[str] = mapped_column(ForeignKey("sourcing_inputs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    as_of_date: Mapped[date] = mapped_column(Date)
    rule_revision: Mapped[int] = mapped_column(Integer)
    comparison_version: Mapped[str] = mapped_column(String(100))
    basis: Mapped[str] = mapped_column(String(40))
    request_snapshot: Mapped[dict] = mapped_column(JSON)
    sourcing_input_snapshot: Mapped[dict] = mapped_column(JSON)
    product_snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class SellerPricingReview(Base):
    __tablename__ = "seller_pricing_reviews"
    __table_args__ = (
        CheckConstraint(
            "basis = 'seller_reported_unverified'",
            name="ck_seller_pricing_reviews_basis",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_on: Mapped[date] = mapped_column(Date)
    review_version: Mapped[str] = mapped_column(String(100))
    basis: Mapped[str] = mapped_column(String(40))
    request_snapshot: Mapped[dict] = mapped_column(JSON)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class PassportDraft(Base):
    __tablename__ = "passport_drafts"
    __table_args__ = (CheckConstraint("revision >= 1", name="ck_passport_drafts_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    content: Mapped[dict] = mapped_column(JSON)


class PassportPublication(Base):
    __tablename__ = "passport_publications"
    __table_args__ = (
        UniqueConstraint("draft_id", "draft_revision", name="uq_passport_draft_revision"),
        CheckConstraint("draft_revision >= 1", name="ck_passport_publications_revision"),
        CheckConstraint(
            "state IN ('published', 'withdrawn', 'superseded')",
            name="ck_passport_publications_state",
        ),
        Index(
            "uq_passport_active_product",
            "product_id",
            unique=True,
            sqlite_where=text("state = 'published'"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    draft_id: Mapped[str] = mapped_column(ForeignKey("passport_drafts.id"), index=True)
    approved_by_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    draft_revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="ck_marketplace_listings_revision"),
        CheckConstraint(
            "state IN ('draft', 'active', 'inactive')",
            name="ck_marketplace_listings_state",
        ),
        CheckConstraint("price_minor IS NULL OR price_minor > 0", name="ck_listing_price_minor"),
        CheckConstraint(
            "state != 'active' OR (published_revision IS NOT NULL "
            "AND published_publication_id IS NOT NULL AND approved_by_account_id IS NOT NULL "
            "AND published_at IS NOT NULL AND public_payload IS NOT NULL "
            "AND payload_hash IS NOT NULL AND price_minor IS NOT NULL)",
            name="ck_marketplace_listings_approved",
        ),
        Index("ix_listing_browse", "state", "product_type", "published_at"),
        Index("ix_listing_location", "state", "location_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), unique=True)
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    content: Mapped[dict] = mapped_column(JSON)
    published_revision: Mapped[int | None] = mapped_column(Integer)
    published_publication_id: Mapped[str | None] = mapped_column(
        ForeignKey("passport_publications.id")
    )
    approved_by_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    public_payload: Mapped[dict | None] = mapped_column(JSON)
    product_type: Mapped[str | None] = mapped_column(String(20))
    search_text: Mapped[str | None] = mapped_column(Text)
    location_key: Mapped[str | None] = mapped_column(String(200))
    price_minor: Mapped[int | None] = mapped_column(Integer)


class ProductReview(Base):
    __tablename__ = "product_reviews"
    __table_args__ = (
        UniqueConstraint("buyer_account_id", "product_id", name="uq_review_buyer_product"),
        CheckConstraint("revision >= 1", name="ck_product_review_revision"),
        CheckConstraint("state IN ('published', 'withdrawn')", name="ck_product_review_state"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_product_review_rating"),
        CheckConstraint("length(text) BETWEEN 1 AND 2000", name="ck_product_review_text"),
        Index("ix_review_product_public", "product_id", "state", "created_at", "id"),
        Index("ix_review_author_created", "buyer_account_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    buyer_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    listing_id: Mapped[str] = mapped_column(ForeignKey("marketplace_listings.id"))
    order_line_id: Mapped[str] = mapped_column(ForeignKey("order_lines.id"))
    purchase_capture_id: Mapped[str] = mapped_column(String(64))
    purchase_verified_at: Mapped[datetime] = mapped_column(DateTime)
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(10))
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PickupFulfillmentEvent(Base):
    __tablename__ = "pickup_fulfillment_events"
    __table_args__ = (
        UniqueConstraint("order_id", "revision", name="uq_pickup_order_revision"),
        CheckConstraint("revision >= 1", name="ck_pickup_revision"),
        CheckConstraint(
            "state IN ('preparing', 'ready_for_pickup', 'collected')", name="ck_pickup_state"
        ),
        CheckConstraint(
            "pickup_instructions IS NULL OR length(pickup_instructions) BETWEEN 1 AND 2000",
            name="ck_pickup_instructions",
        ),
        CheckConstraint(
            "state = 'preparing' OR pickup_instructions IS NOT NULL",
            name="ck_pickup_ready_instructions",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))
    pickup_instructions: Mapped[str | None] = mapped_column(Text)
    recorded_by_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ProductPhoto(Base):
    __tablename__ = "product_photos"
    __table_args__ = (
        CheckConstraint(
            "width BETWEEN 1 AND 2048 AND height BETWEEN 1 AND 2048", name="ck_photo_dimensions"
        ),
        CheckConstraint(
            "byte_count BETWEEN 1 AND 4194304 AND length(image_bytes) = byte_count",
            name="ck_photo_size",
        ),
        CheckConstraint("length(sha256) = 64", name="ck_photo_hash"),
        Index("ix_photo_product_created", "product_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    byte_count: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    image_bytes: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)


class ListingPhoto(Base):
    __tablename__ = "listing_photos"
    listing_id: Mapped[str] = mapped_column(ForeignKey("marketplace_listings.id"), primary_key=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey("product_photos.id"), primary_key=True)
    __table_args__ = (Index("ix_listing_photo_public", "photo_id", "listing_id"),)


class Storefront(Base):
    __tablename__ = "storefronts"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_storefront_account"),
        CheckConstraint("revision >= 1", name="ck_storefront_revision"),
        CheckConstraint("state IN ('draft', 'published', 'withdrawn')", name="ck_storefront_state"),
        CheckConstraint(
            "published_revision IS NULL OR "
            "(published_revision >= 1 AND published_revision <= revision)",
            name="ck_storefront_published_revision",
        ),
        CheckConstraint(
            "state != 'published' OR (published_revision IS NOT NULL "
            "AND published_at IS NOT NULL AND payload_hash IS NOT NULL "
            "AND public_payload IS NOT NULL AND search_text IS NOT NULL)",
            name="ck_storefront_published",
        ),
        Index("ix_storefront_browse", "state", "published_at", "id"),
        Index("ix_storefront_location", "state", "location_key", "published_at"),
    )
    # Distinct public IDs keep the resource stable if account cardinality grows later.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    content: Mapped[dict] = mapped_column(JSON)
    published_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    public_payload: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_key: Mapped[str | None] = mapped_column(String(200), nullable=True)


class StorefrontDiscoveryLocation(Base):
    __tablename__ = "storefront_discovery_locations"
    __table_args__ = (
        CheckConstraint("latitude_hundredths BETWEEN -9000 AND 9000", name="ck_discovery_latitude"),
        CheckConstraint(
            "longitude_hundredths BETWEEN -18000 AND 18000", name="ck_discovery_longitude"
        ),
        Index("ix_discovery_area", "latitude_hundredths", "longitude_hundredths"),
    )
    storefront_id: Mapped[str] = mapped_column(ForeignKey("storefronts.id"), primary_key=True)
    latitude_hundredths: Mapped[int] = mapped_column(Integer)
    longitude_hundredths: Mapped[int] = mapped_column(Integer)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("account_id", "listing_id", name="uq_favorite_account_listing"),
        Index("ix_favorite_account_created", "account_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    listing_id: Mapped[str] = mapped_column(ForeignKey("marketplace_listings.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SellableInventory(Base):
    __tablename__ = "sellable_inventory"
    __table_args__ = (
        CheckConstraint(
            "on_hand >= 0 AND on_hand <= 1000000", name="ck_sellable_inventory_quantity"
        ),
        CheckConstraint("revision >= 1", name="ck_sellable_inventory_revision"),
    )
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    selling_unit: Mapped[str] = mapped_column(String(200))
    on_hand: Mapped[int] = mapped_column(Integer)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("buyer_account_id", "idempotency_key", name="uq_order_buyer_key"),
        CheckConstraint("status IN ('pending_payment', 'cancelled')", name="ck_orders_status"),
        CheckConstraint(
            "subtotal_minor > 0 AND subtotal_minor <= 100000000000",
            name="ck_orders_subtotal",
        ),
        CheckConstraint("expires_at > created_at", name="ck_orders_deadline"),
        CheckConstraint(
            "buyer_account_id != seller_account_id", name="ck_orders_different_accounts"
        ),
        Index("ix_order_buyer_created", "buyer_account_id", "created_at"),
        Index("ix_order_seller_created", "seller_account_id", "created_at"),
        Index("ix_order_reservations", "status", "expires_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    buyer_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    seller_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    idempotency_key: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    subtotal_minor: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    checkout: Mapped[PayPalCheckout | None] = relationship(uselist=False)
    refund_request: Mapped[RefundRequest | None] = relationship(uselist=False)


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "listing_id", name="uq_order_line_listing"),
        CheckConstraint("quantity >= 1 AND quantity <= 10000", name="ck_order_line_quantity"),
        CheckConstraint("unit_price_minor > 0", name="ck_order_line_price"),
        CheckConstraint(
            "subtotal_minor = unit_price_minor * quantity",
            name="ck_order_line_subtotal",
        ),
        Index("ix_order_line_stock", "product_id", "order_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    listing_id: Mapped[str] = mapped_column(ForeignKey("marketplace_listings.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    subtotal_minor: Mapped[int] = mapped_column(Integer)


class PayPalCheckout(Base):
    __tablename__ = "paypal_checkouts"
    __table_args__ = (
        Index("ix_paypal_checkout_verified", "verified_at", "order_id"),
        CheckConstraint(
            "state IN ('creating', 'ready', 'capture_pending', "
            "'completed', 'failed', 'needs_review')",
            name="ck_paypal_checkout_state",
        ),
        CheckConstraint(
            "amount_minor > 0 AND amount_minor <= 100000000000",
            name="ck_paypal_checkout_amount",
        ),
        CheckConstraint(
            "(lease_token IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_paypal_checkout_lease",
        ),
        CheckConstraint(
            "state != 'completed' OR (capture_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_paypal_checkout_completed",
        ),
    )
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String(13))
    amount_minor: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    create_request_id: Mapped[str] = mapped_column(String(36), default=new_id, unique=True)
    capture_request_id: Mapped[str] = mapped_column(String(36), default=new_id, unique=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    provider_status: Mapped[str | None] = mapped_column(String(32))
    capture_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    capture_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    fee_minor: Mapped[int | None] = mapped_column(Integer)
    net_minor: Mapped[int | None] = mapped_column(Integer)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class RefundRequest(Base):
    __tablename__ = "refund_requests"
    __table_args__ = (
        CheckConstraint(
            "state IN ('requested', 'denied', 'refund_pending', "
            "'refunded', 'failed', 'needs_review')",
            name="ck_refund_request_state",
        ),
        CheckConstraint("revision >= 1", name="ck_refund_request_revision"),
        CheckConstraint(
            "amount_minor > 0 AND amount_minor <= 100000000000",
            name="ck_refund_request_amount",
        ),
        CheckConstraint(
            "(state = 'requested' AND decision IS NULL) OR "
            "(state = 'denied' AND decision IS NOT NULL "
            "AND decision = 'denied' AND decision_reason IS NOT NULL) OR "
            "(state IN ('refund_pending', 'refunded', 'failed', 'needs_review') "
            "AND decision IS NOT NULL AND decision = 'approved')",
            name="ck_refund_request_decision_state",
        ),
        CheckConstraint(
            "decision IS NULL OR (decided_at IS NOT NULL AND "
            "decided_by_account_id IS NOT NULL AND decision_revision IS NOT NULL)",
            name="ck_refund_request_decision_audit",
        ),
        CheckConstraint(
            "state != 'refunded' OR (provider_refund_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_refund_request_completed",
        ),
        CheckConstraint(
            "(lease_token IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_refund_request_lease",
        ),
        Index("ix_refund_request_created", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True)
    requested_by_account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reason: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))
    decision: Mapped[str | None] = mapped_column(String(8))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decision_revision: Mapped[int | None] = mapped_column(Integer)
    decided_by_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    amount_minor: Mapped[int] = mapped_column(Integer)
    merchant_id: Mapped[str] = mapped_column(String(13))
    capture_id: Mapped[str] = mapped_column(ForeignKey("paypal_checkouts.capture_id"))
    provider_order_id: Mapped[str] = mapped_column(String(64))
    provider_request_id: Mapped[str] = mapped_column(String(36), default=new_id, unique=True)
    provider_refund_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    provider_status: Mapped[str | None] = mapped_column(String(20))
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
