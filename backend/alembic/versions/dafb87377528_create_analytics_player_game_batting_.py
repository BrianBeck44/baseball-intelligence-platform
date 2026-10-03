"""create analytics player_game_batting table

Revision ID: dafb87377528
Revises: e4f8b2a91c73
Create Date: 2026-10-02 22:15:55.613558

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dafb87377528"
down_revision: Union[str, Sequence[str], None] = "e4f8b2a91c73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics.player_game_batting."""
    op.create_table(
        "player_game_batting",
        sa.Column(
            "player_game_batting_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("plate_appearances", sa.Integer(), nullable=False),
        sa.Column("at_bats", sa.Integer(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.Column("singles", sa.Integer(), nullable=False),
        sa.Column("doubles", sa.Integer(), nullable=False),
        sa.Column("triples", sa.Integer(), nullable=False),
        sa.Column("home_runs", sa.Integer(), nullable=False),
        sa.Column("walks", sa.Integer(), nullable=False),
        sa.Column("hit_by_pitch", sa.Integer(), nullable=False),
        sa.Column("strikeouts", sa.Integer(), nullable=False),
        sa.Column("sacrifice_flies", sa.Integer(), nullable=False),
        sa.Column("sacrifice_bunts", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "player_game_batting_id",
            name="pk_player_game_batting",
        ),
        sa.UniqueConstraint(
            "player_id",
            "game_id",
            "team_id",
            name="uq_player_game_batting_player_game_team",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["curated.player.player_id"],
            name="fk_player_game_batting_player",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["curated.game.game_id"],
            name="fk_player_game_batting_game",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["curated.team.team_id"],
            name="fk_player_game_batting_team",
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "team_id"],
            ["curated.game_team.game_id", "curated.game_team.team_id"],
            name="fk_player_game_batting_game_team",
        ),
        sa.CheckConstraint(
            "plate_appearances >= 0",
            name="ck_player_game_batting_plate_appearances",
        ),
        sa.CheckConstraint(
            "at_bats >= 0",
            name="ck_player_game_batting_at_bats",
        ),
        sa.CheckConstraint(
            "hits >= 0",
            name="ck_player_game_batting_hits",
        ),
        sa.CheckConstraint(
            "singles >= 0",
            name="ck_player_game_batting_singles",
        ),
        sa.CheckConstraint(
            "doubles >= 0",
            name="ck_player_game_batting_doubles",
        ),
        sa.CheckConstraint(
            "triples >= 0",
            name="ck_player_game_batting_triples",
        ),
        sa.CheckConstraint(
            "home_runs >= 0",
            name="ck_player_game_batting_home_runs",
        ),
        sa.CheckConstraint(
            "walks >= 0",
            name="ck_player_game_batting_walks",
        ),
        sa.CheckConstraint(
            "hit_by_pitch >= 0",
            name="ck_player_game_batting_hit_by_pitch",
        ),
        sa.CheckConstraint(
            "strikeouts >= 0",
            name="ck_player_game_batting_strikeouts",
        ),
        sa.CheckConstraint(
            "sacrifice_flies >= 0",
            name="ck_player_game_batting_sacrifice_flies",
        ),
        sa.CheckConstraint(
            "sacrifice_bunts >= 0",
            name="ck_player_game_batting_sacrifice_bunts",
        ),
        schema="analytics",
    )


def downgrade() -> None:
    """Drop analytics.player_game_batting."""
    op.drop_table("player_game_batting", schema="analytics")
