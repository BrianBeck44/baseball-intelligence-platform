"""create curated game team table

Revision ID: a3024cf4ca66
Revises: 7747c1601a99
Create Date: 2026-09-24 21:43:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3024cf4ca66"
down_revision: Union[str, Sequence[str], None] = "7747c1601a99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated.game_team."""
    op.create_table(
        "game_team",
        sa.Column(
            "game_team_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("home_away", sa.String(4), nullable=False),
        sa.PrimaryKeyConstraint("game_team_id", name="pk_game_team"),
        sa.UniqueConstraint("game_id", "team_id", name="uq_game_team_game_team"),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["curated.game.game_id"],
            name="fk_game_team_game",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["curated.team.team_id"],
            name="fk_game_team_team",
        ),
        sa.CheckConstraint(
            "home_away IN ('HOME', 'AWAY')",
            name="ck_game_team_home_away",
        ),
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated.game_team."""
    op.drop_table("game_team", schema="curated")
