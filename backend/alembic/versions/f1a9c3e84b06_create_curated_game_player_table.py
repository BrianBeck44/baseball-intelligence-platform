"""create curated game player table

Revision ID: f1a9c3e84b06
Revises: a3024cf4ca66
Create Date: 2026-09-25 15:16:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a9c3e84b06"
down_revision: Union[str, Sequence[str], None] = "a3024cf4ca66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated.game_player."""
    op.create_table(
        "game_player",
        sa.Column(
            "game_player_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("game_player_id", name="pk_game_player"),
        sa.UniqueConstraint(
            "game_id",
            "player_id",
            "team_id",
            name="uq_game_player_game_player_team",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["curated.game.game_id"],
            name="fk_game_player_game",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["curated.player.player_id"],
            name="fk_game_player_player",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["curated.team.team_id"],
            name="fk_game_player_team",
        ),
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated.game_player."""
    op.drop_table("game_player", schema="curated")
