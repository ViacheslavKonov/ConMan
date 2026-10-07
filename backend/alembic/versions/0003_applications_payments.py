"""applications and payments

Revision ID: 0003_applications_payments
Revises: 0002_core
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_applications_payments"
down_revision: Union[str, Sequence[str], None] = "0002_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE payment_code_seq START WITH 1 INCREMENT BY 1")

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payment_type", sa.String(16), nullable=False),
        sa.Column(
            "payment_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(32), nullable=False),
        sa.Column("reference", sa.String(250), nullable=True),
        sa.Column("client_operation_id", sa.String(100), nullable=True, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="CONFIRMED"),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "payment_type IN ('PAYMENT','REFUND')",
            name="ck_payments_type",
        ),
        sa.CheckConstraint(
            "payment_method IN ('CASH','CARD','TRANSFER','SBP','OTHER')",
            name="ck_payments_method",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','CONFIRMED','CANCELLED','REFUNDED')",
            name="ck_payments_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount"),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])
    op.create_index("ix_payments_event_id", "payments", ["event_id"])
    op.create_index("ix_payments_date", "payments", ["payment_date"])


def downgrade() -> None:
    op.drop_table("payments")
    op.execute("DROP SEQUENCE IF EXISTS payment_code_seq")
