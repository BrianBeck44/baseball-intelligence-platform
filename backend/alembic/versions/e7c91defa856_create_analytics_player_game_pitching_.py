"""create analytics player_game_pitching table

Revision ID: e7c91defa856
Revises: dafb87377528
Create Date: 2026-10-03 16:48:38.203901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7c91defa856"
down_revision: Union[str, Sequence[str], None] = "dafb87377528"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics.player_game_pitching."""
    op.create_table(
        "player_game_pitching",
        sa.Column(
            "player_game_pitching_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("pitcher_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("batters_faced", sa.Integer(), nullable=False),
        sa.Column("pitches", sa.Integer(), nullable=False),
        sa.Column("hits_allowed", sa.Integer(), nullable=False),
        sa.Column("home_runs_allowed", sa.Integer(), nullable=False),
        sa.Column("walks", sa.Integer(), nullable=False),
        sa.Column("hit_by_pitch", sa.Integer(), nullable=False),
        sa.Column("strikeouts", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "player_game_pitching_id",
            name="pk_player_game_pitching",
        ),
        sa.UniqueConstraint(
            "pitcher_id",
            "game_id",
            "team_id",
            name="uq_player_game_pitching_pitcher_game_team",
        ),
        sa.ForeignKeyConstraint(
            ["pitcher_id"],
            ["curated.player.player_id"],
            name="fk_player_game_pitching_player",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["curated.game.game_id"],
            name="fk_player_game_pitching_game",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["curated.team.team_id"],
            name="fk_player_game_pitching_team",
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "team_id"],
            ["curated.game_team.game_id", "curated.game_team.team_id"],
            name="fk_player_game_pitching_game_team",
        ),
        sa.CheckConstraint(
            "batters_faced >= 0",
            name="ck_player_game_pitching_batters_faced",
        ),
        sa.CheckConstraint(
            "pitches >= 0",
            name="ck_player_game_pitching_pitches",
        ),
        sa.CheckConstraint(
            "hits_allowed >= 0",
            name="ck_player_game_pitching_hits_allowed",
        ),
        sa.CheckConstraint(
            "home_runs_allowed >= 0",
            name="ck_player_game_pitching_home_runs_allowed",
        ),
        sa.CheckConstraint(
            "walks >= 0",
            name="ck_player_game_pitching_walks",
        ),
        sa.CheckConstraint(
            "hit_by_pitch >= 0",
            name="ck_player_game_pitching_hit_by_pitch",
        ),
        sa.CheckConstraint(
            "strikeouts >= 0",
            name="ck_player_game_pitching_strikeouts",
        ),
        schema="analytics",
    )


def downgrade() -> None:
    """Drop analytics.player_game_pitching."""
    op.drop_table("player_game_pitching", schema="analytics")
