"""add ingestion batch counters and status check

Revision ID: e02a844d7b54
Revises: 8886697392cb
Create Date: 2026-09-17 13:22:32.034807

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e02a844d7b54"
down_revision: Union[str, Sequence[str], None] = "8886697392cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add filtered/skipped counters and status vocabulary to raw.ingestion_batch."""
    op.add_column(
        "ingestion_batch",
        sa.Column(
            "records_filtered",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema="raw",
    )
    op.add_column(
        "ingestion_batch",
        sa.Column(
            "records_skipped",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema="raw",
    )
    op.create_check_constraint(
        "ck_ingestion_batch_records_filtered",
        "ingestion_batch",
        "records_filtered >= 0",
        schema="raw",
    )
    op.create_check_constraint(
        "ck_ingestion_batch_records_skipped",
        "ingestion_batch",
        "records_skipped >= 0",
        schema="raw",
    )
    op.create_check_constraint(
        "ck_ingestion_batch_status",
        "ingestion_batch",
        "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
        schema="raw",
    )


def downgrade() -> None:
    """Remove filtered/skipped counters and status vocabulary."""
    op.drop_constraint(
        "ck_ingestion_batch_status",
        "ingestion_batch",
        schema="raw",
        type_="check",
    )
    op.drop_constraint(
        "ck_ingestion_batch_records_filtered",
        "ingestion_batch",
        schema="raw",
        type_="check",
    )
    op.drop_constraint(
        "ck_ingestion_batch_records_skipped",
        "ingestion_batch",
        schema="raw",
        type_="check",
    )
    op.drop_column("ingestion_batch", "records_filtered", schema="raw")
    op.drop_column("ingestion_batch", "records_skipped", schema="raw")
