"""create analytics player_season_pitching table

Revision ID: d4c91a7e2b08
Revises: c8a4f2d19b70
Create Date: 2026-10-04 17:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4c91a7e2b08"
down_revision: Union[str, Sequence[str], None] = "c8a4f2d19b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics.player_season_pitching."""
    op.create_table(
        "player_season_pitching",
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("season_id", sa.BigInteger(), nullable=False),
        sa.Column("games", sa.Integer(), nullable=False),
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
            "player_id",
            "season_id",
            name="pk_player_season_pitching",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["curated.player.player_id"],
            name="fk_player_season_pitching_player",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["curated.season.season_id"],
            name="fk_player_season_pitching_season",
        ),
        sa.CheckConstraint(
            "games >= 0",
            name="ck_player_season_pitching_games",
        ),
        sa.CheckConstraint(
            "batters_faced >= 0",
            name="ck_player_season_pitching_batters_faced",
        ),
        sa.CheckConstraint(
            "pitches >= 0",
            name="ck_player_season_pitching_pitches",
        ),
        sa.CheckConstraint(
            "hits_allowed >= 0",
            name="ck_player_season_pitching_hits_allowed",
        ),
        sa.CheckConstraint(
            "home_runs_allowed >= 0",
            name="ck_player_season_pitching_home_runs_allowed",
        ),
        sa.CheckConstraint(
            "walks >= 0",
            name="ck_player_season_pitching_walks",
        ),
        sa.CheckConstraint(
            "hit_by_pitch >= 0",
            name="ck_player_season_pitching_hit_by_pitch",
        ),
        sa.CheckConstraint(
            "strikeouts >= 0",
            name="ck_player_season_pitching_strikeouts",
        ),
        schema="analytics",
    )


def downgrade() -> None:
    """Drop analytics.player_season_pitching."""
    op.drop_table("player_season_pitching", schema="analytics")
