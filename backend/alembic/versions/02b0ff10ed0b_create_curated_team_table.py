"""create curated team table

Revision ID: 02b0ff10ed0b
Revises: b7f59c9e7bea
Create Date: 2026-09-24 19:39:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "02b0ff10ed0b"
down_revision: Union[str, Sequence[str], None] = "b7f59c9e7bea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated.team."""
    op.create_table(
        "team",
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("team_id", name="pk_team"),
        sa.UniqueConstraint("code", name="uq_team_code"),
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated.team."""
    op.drop_table("team", schema="curated")
