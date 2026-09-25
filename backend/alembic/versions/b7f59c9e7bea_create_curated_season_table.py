"""create curated season table

Revision ID: b7f59c9e7bea
Revises: e02a844d7b54
Create Date: 2026-09-24 19:21:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f59c9e7bea"
down_revision: Union[str, Sequence[str], None] = "e02a844d7b54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated.season."""
    op.create_table(
        "season",
        sa.Column(
            "season_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("season_year", sa.SmallInteger(), nullable=False),
        sa.Column("all_star_date", sa.Date(), nullable=True),
        sa.Column("trade_deadline_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("season_id", name="pk_season"),
        sa.UniqueConstraint("season_year", name="uq_season_year"),
        
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated.season."""
    op.drop_table("season", schema="curated")
