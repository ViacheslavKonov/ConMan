"""core business entities

Revision ID: 0002_core
Revises: 0001_foundation
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_core"
down_revision: Union[str, Sequence[str], None] = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in [
        "event_code_seq",
        "vendor_code_seq",
        "tariff_code_seq",
        "booking_code_seq",
        "participant_code_seq",
        "booking_participant_code_seq",
        "charge_code_seq",
    ]:
        op.execute(f"CREATE SEQUENCE {name} START WITH 1 INCREMENT BY 1")

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(500), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("event_name", sa.String(250), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("venue", sa.String(250), nullable=True),
        sa.Column("city", sa.String(150), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("registration_open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vendor_checkin_open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('DRAFT','REGISTRATION','ACTIVE','CLOSED','ARCHIVED')",
            name="ck_events_status",
        ),
        sa.CheckConstraint(
            "end_date >= start_date",
            name="ck_events_dates",
        ),
    )
    op.create_index("ix_events_status", "events", ["status"])

    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("vendor_name", sa.String(250), nullable=False),
        sa.Column("legal_name", sa.String(250), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(100), nullable=True),
        sa.Column("telegram", sa.String(150), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("social_link", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vendors_vendor_name", "vendors", ["vendor_name"])
    op.create_index("ix_vendors_email", "vendors", ["email"])

    op.create_table(
        "participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("last_name", sa.String(150), nullable=False),
        sa.Column("first_name", sa.String(150), nullable=False),
        sa.Column("middle_name", sa.String(150), nullable=True),
        sa.Column("nickname", sa.String(150), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(100), nullable=True),
        sa.Column("telegram", sa.String(150), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_participants_nickname", "participants", ["nickname"])
    op.create_index("ix_participants_name", "participants", ["last_name", "first_name"])

    op.create_table(
        "tariffs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tariff_name", sa.String(250), nullable=False),
        sa.Column("booking_type", sa.String(16), nullable=False),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("included_helpers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra_participant_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("booking_type IN ('FULL','HALF')", name="ck_tariffs_booking_type"),
        sa.CheckConstraint("base_price >= 0", name="ck_tariffs_base_price"),
        sa.CheckConstraint("included_helpers >= 0", name="ck_tariffs_helpers"),
        sa.CheckConstraint("extra_participant_price >= 0", name="ck_tariffs_extra_price"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_tariffs_dates"),
    )
    op.create_index("ix_tariffs_event_id", "tariffs", ["event_id"])

    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tariff_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tariffs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("booking_type", sa.String(16), nullable=False),
        sa.Column("booking_status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("application_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("included_helpers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra_participant_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("participants_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("included_participants_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra_participants_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extras_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("manual_adjustment", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("calculated_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("final_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payment_status", sa.String(32), nullable=False, server_default="UNPAID"),
        sa.Column("seating_status", sa.String(32), nullable=False, server_default="UNASSIGNED"),
        sa.Column("checkin_status", sa.String(32), nullable=False, server_default="NONE"),
        sa.Column("pricing_locked", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("booking_type IN ('FULL','HALF')", name="ck_bookings_type"),
        sa.CheckConstraint(
            "booking_status IN ('DRAFT','SUBMITTED','APPROVED','AWAITING_PAYMENT','CONFIRMED','CANCELLED','REJECTED')",
            name="ck_bookings_status",
        ),
    )
    op.create_index("ix_bookings_event_id", "bookings", ["event_id"])
    op.create_index("ix_bookings_vendor_id", "bookings", ["vendor_id"])
    op.create_index("ix_bookings_status", "bookings", ["booking_status"])

    op.create_table(
        "booking_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_included", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("charge_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("registration_status", sa.String(32), nullable=False, server_default="REGISTERED"),
        sa.Column("checkin_status", sa.String(32), nullable=False, server_default="NOT_CHECKED_IN"),
        sa.Column("checkin_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkin_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("badge_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("badge_issued", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("badge_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('OWNER','HELPER')", name="ck_booking_participants_role"),
        sa.CheckConstraint(
            "registration_status IN ('DRAFT','REGISTERED','CANCELLED')",
            name="ck_booking_participants_registration",
        ),
        sa.CheckConstraint(
            "checkin_status IN ('NOT_CHECKED_IN','CHECKED_IN')",
            name="ck_booking_participants_checkin",
        ),
        sa.UniqueConstraint("booking_id", "participant_id", name="uq_booking_participant"),
    )
    op.create_index("ix_booking_participants_booking_id", "booking_participants", ["booking_id"])
    op.create_index(
        "ux_booking_active_owner",
        "booking_participants",
        ["booking_id"],
        unique=True,
        postgresql_where=sa.text("role = 'OWNER' AND registration_status <> 'CANCELLED'"),
    )

    op.create_table(
        "charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("charge_type", sa.String(32), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("automatic", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_id", sa.String(100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "charge_type IN ('TABLE','EXTRA_PARTICIPANT','DISCOUNT','SURCHARGE','MANUAL')",
            name="ck_charges_type",
        ),
    )
    op.create_index("ix_charges_booking_id", "charges", ["booking_id"])


def downgrade() -> None:
    op.drop_table("charges")
    op.drop_table("booking_participants")
    op.drop_table("bookings")
    op.drop_table("tariffs")
    op.drop_table("participants")
    op.drop_table("vendors")
    op.drop_table("events")
    op.drop_table("app_settings")

    for name in [
        "charge_code_seq",
        "booking_participant_code_seq",
        "participant_code_seq",
        "booking_code_seq",
        "tariff_code_seq",
        "vendor_code_seq",
        "event_code_seq",
    ]:
        op.execute(f"DROP SEQUENCE IF EXISTS {name}")
