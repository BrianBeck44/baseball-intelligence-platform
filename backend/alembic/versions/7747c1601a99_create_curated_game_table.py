"""create curated game table

Revision ID: 7747c1601a99
Revises: 282f1783779f
Create Date: 2026-09-24 21:31:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7747c1601a99"
down_revision: Union[str, Sequence[str], None] = "282f1783779f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated.game."""
    op.create_table(
        "game",
        sa.Column(
            "game_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("mlb_game_pk", sa.BigInteger(), nullable=False),
        sa.Column("season_id", sa.BigInteger(), nullable=False),
        sa.Column("official_game_date", sa.Date(), nullable=False),
        sa.Column("game_type_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("game_id", name="pk_game"),
        sa.UniqueConstraint("mlb_game_pk", name="uq_game_mlb_game_pk"),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["curated.season.season_id"],
            name="fk_game_season",
        ),
        sa.ForeignKeyConstraint(
            ["game_type_id"],
            ["curated.game_type.id"],
            name="fk_game_game_type",
        ),
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated.game."""
    op.drop_table("game", schema="curated")
