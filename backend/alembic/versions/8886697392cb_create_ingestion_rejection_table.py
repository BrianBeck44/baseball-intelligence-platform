"""create ingestion rejection table

Revision ID: 8886697392cb
Revises: 20388e16a800
Create Date: 2026-09-15 21:30:34.025981

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8886697392cb"
down_revision: Union[str, Sequence[str], None] = "20388e16a800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create raw.ingestion_rejection."""
    op.create_table(
        "ingestion_rejection",
        sa.Column(
            "ingestion_rejection_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("ingestion_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=False),
        sa.Column("source_key", postgresql.JSONB(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("raw_row", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint(
            "ingestion_rejection_id",
            name="pk_ingestion_rejection",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["raw.ingestion_batch.ingestion_batch_id"],
            name="fk_ingestion_rejection_ingestion_batch",
        ),
        sa.CheckConstraint(
            "rejection_reason IN ("
            "'MISSING_REQUIRED_FIELD', "
            "'INVALID_SOURCE_KEY', "
            "'DUPLICATE_SOURCE_KEY'"
            ")",
            name="ck_ingestion_rejection_reason",
        ),
        schema="raw",
    )
    op.create_index(
        "ix_ingestion_rejection_batch",
        "ingestion_rejection",
        ["ingestion_batch_id"],
        schema="raw",
    )
    op.create_index(
        "ix_ingestion_rejection_batch_row",
        "ingestion_rejection",
        ["ingestion_batch_id", "source_row_number"],
        schema="raw",
    )


def downgrade() -> None:
    """Drop raw.ingestion_rejection."""
    op.drop_index(
        "ix_ingestion_rejection_batch_row",
        table_name="ingestion_rejection",
        schema="raw",
    )
    op.drop_index(
        "ix_ingestion_rejection_batch",
        table_name="ingestion_rejection",
        schema="raw",
    )
    op.drop_table("ingestion_rejection", schema="raw")
