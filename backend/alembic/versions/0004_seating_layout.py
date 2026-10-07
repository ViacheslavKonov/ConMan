"""seating layout

Revision ID: 0004_seating_layout
Revises: 0003_applications_payments
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_seating_layout"
down_revision: Union[str, Sequence[str], None] = "0003_applications_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE zone_code_seq START WITH 1 INCREMENT BY 1")
    op.execute("CREATE SEQUENCE table_layout_code_seq START WITH 1 INCREMENT BY 1")
    op.execute("CREATE SEQUENCE table_assignment_code_seq START WITH 1 INCREMENT BY 1")

    op.create_table(
        "layout_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("zone_name", sa.String(250), nullable=False),
        sa.Column("zone_type", sa.String(32), nullable=False, server_default="GENERAL"),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("x", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("y", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer(), nullable=False, server_default="280"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="160"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_layout_zones_event_id", "layout_zones", ["event_id"])

    op.create_table(
        "layout_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "zone_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("layout_zones.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("table_number", sa.Integer(), nullable=False),
        sa.Column("table_label", sa.String(50), nullable=False),
        sa.Column("capacity_slots", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("x", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("y", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="54"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("event_id", "table_number", name="uq_layout_tables_event_number"),
    )
    op.create_index("ix_layout_tables_event_id", "layout_tables", ["event_id"])
    op.create_index("ix_layout_tables_zone_id", "layout_tables", ["zone_id"])

    op.create_table(
        "table_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("layout_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("start_slot", sa.Integer(), nullable=False),
        sa.Column("slot_count", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("start_slot >= 1", name="ck_table_assignments_start_slot"),
        sa.CheckConstraint("slot_count >= 1", name="ck_table_assignments_slot_count"),
    )
    op.create_index("ix_table_assignments_event_id", "table_assignments", ["event_id"])
    op.create_index("ix_table_assignments_table_id", "table_assignments", ["table_id"])


def downgrade() -> None:
    op.drop_table("table_assignments")
    op.drop_table("layout_tables")
    op.drop_table("layout_zones")
    op.execute("DROP SEQUENCE IF EXISTS table_assignment_code_seq")
    op.execute("DROP SEQUENCE IF EXISTS table_layout_code_seq")
    op.execute("DROP SEQUENCE IF EXISTS zone_code_seq")
