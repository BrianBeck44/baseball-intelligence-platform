"""create curated player table

Revision ID: 282f1783779f
Revises: 02b0ff10ed0b
Create Date: 2026-09-24 20:04:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "282f1783779f"
down_revision: Union[str, Sequence[str], None] = "02b0ff10ed0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated.player."""
    op.create_table(
        "player",
        sa.Column(
            "player_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("mlb_player_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.PrimaryKeyConstraint("player_id", name="pk_player"),
        sa.UniqueConstraint("mlb_player_id", name="uq_player_mlb_player_id"),
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated.player."""
    op.drop_table("player", schema="curated")
