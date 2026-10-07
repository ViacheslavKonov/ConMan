"""check-in and badge log

Revision ID: 0005_checkin_badges
Revises: 0004_seating_layout
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_checkin_badges"
down_revision: Union[str, Sequence[str], None] = "0004_seating_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE checkin_log_code_seq START WITH 1 INCREMENT BY 1")

    op.create_table(
        "checkin_logs",
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
        ),
        sa.Column(
            "participant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "booking_participant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking_participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "action IN ('CHECK_IN','CHECK_IN_CANCELLED','BADGE_ISSUED','BADGE_REPLACED')",
            name="ck_checkin_logs_action",
        ),
    )
    op.create_index("ix_checkin_logs_event_id", "checkin_logs", ["event_id"])
    op.create_index("ix_checkin_logs_booking_id", "checkin_logs", ["booking_id"])
    op.create_index(
        "ix_checkin_logs_booking_participant_id",
        "checkin_logs",
        ["booking_participant_id"],
    )
    op.create_index("ix_checkin_logs_timestamp", "checkin_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_table("checkin_logs")
    op.execute("DROP SEQUENCE IF EXISTS checkin_log_code_seq")
