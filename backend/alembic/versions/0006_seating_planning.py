"""seating preferences and planning

Revision ID: 0006_seating_planning
Revises: 0005_checkin_badges
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_seating_planning"
down_revision: Union[str, Sequence[str], None] = "0005_checkin_badges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "seating_preferences_open",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.execute("CREATE SEQUENCE seating_preference_code_seq START WITH 1 INCREMENT BY 1")
    op.execute("CREATE SEQUENCE seating_plan_code_seq START WITH 1 INCREMENT BY 1")
    op.execute("CREATE SEQUENCE seating_plan_assignment_code_seq START WITH 1 INCREMENT BY 1")

    op.create_table(
        "seating_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("access_token", sa.String(96), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column(
            "allow_other_tables",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "allow_other_zones",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED')",
            name="ck_seating_preferences_status",
        ),
    )
    op.create_index(
        "ix_seating_preferences_event_id",
        "seating_preferences",
        ["event_id"],
    )

    op.create_table(
        "seating_table_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "preference_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seating_preferences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("layout_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "preference_id",
            "table_id",
            name="uq_seating_table_preference",
        ),
        sa.CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="ck_seating_table_preference_priority",
        ),
    )

    op.create_table(
        "seating_zone_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "preference_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seating_preferences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "zone_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("layout_zones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "preference_id",
            "zone_id",
            name="uq_seating_zone_preference",
        ),
        sa.CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="ck_seating_zone_preference_priority",
        ),
    )

    op.create_table(
        "seating_adjacency_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "preference_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seating_preferences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("preference_type", sa.String(32), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "preference_id",
            "target_booking_id",
            name="uq_seating_adjacency_preference",
        ),
        sa.CheckConstraint(
            "preference_type IN ('MUST_NEAR','PREFER_NEAR','AVOID_NEAR','MUST_NOT_NEAR')",
            name="ck_seating_adjacency_preference_type",
        ),
        sa.CheckConstraint(
            "weight BETWEEN 1 AND 10",
            name="ck_seating_adjacency_preference_weight",
        ),
    )

    op.create_table(
        "seating_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_name", sa.String(250), nullable=False),
        sa.Column("plan_type", sa.String(32), nullable=False, server_default="AUTO"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("score", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("conflicts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unassigned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "plan_type IN ('AUTO','MANUAL','COPY')",
            name="ck_seating_plans_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','FINALIZED','ARCHIVED')",
            name="ck_seating_plans_status",
        ),
    )
    op.create_index(
        "ix_seating_plans_event_id",
        "seating_plans",
        ["event_id"],
    )

    op.create_table(
        "seating_plan_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seating_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        ),
        sa.Column("start_slot", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("slot_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("score", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_by",
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
        sa.UniqueConstraint(
            "plan_id",
            "booking_id",
            name="uq_seating_plan_assignment_booking",
        ),
        sa.CheckConstraint(
            "start_slot >= 1",
            name="ck_seating_plan_assignment_start_slot",
        ),
        sa.CheckConstraint(
            "slot_count BETWEEN 1 AND 2",
            name="ck_seating_plan_assignment_slot_count",
        ),
    )
    op.create_index(
        "ix_seating_plan_assignments_plan_id",
        "seating_plan_assignments",
        ["plan_id"],
    )
    op.create_index(
        "ix_seating_plan_assignments_table_id",
        "seating_plan_assignments",
        ["table_id"],
    )


def downgrade() -> None:
    op.drop_table("seating_plan_assignments")
    op.drop_table("seating_plans")
    op.drop_table("seating_adjacency_preferences")
    op.drop_table("seating_zone_preferences")
    op.drop_table("seating_table_preferences")
    op.drop_table("seating_preferences")

    op.execute("DROP SEQUENCE IF EXISTS seating_plan_assignment_code_seq")
    op.execute("DROP SEQUENCE IF EXISTS seating_plan_code_seq")
    op.execute("DROP SEQUENCE IF EXISTS seating_preference_code_seq")

    op.drop_column("events", "seating_preferences_open")
