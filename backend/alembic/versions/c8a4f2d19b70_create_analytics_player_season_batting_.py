"""create analytics player_season_batting table

Revision ID: c8a4f2d19b70
Revises: 4ebd18810a99
Create Date: 2026-10-03 21:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8a4f2d19b70"
down_revision: Union[str, Sequence[str], None] = "4ebd18810a99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics.player_season_batting."""
    op.create_table(
        "player_season_batting",
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("season_id", sa.BigInteger(), nullable=False),
        sa.Column("games", sa.Integer(), nullable=False),
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
        sa.Column("batting_average", sa.Numeric(7, 6), nullable=True),
        sa.Column("on_base_percentage", sa.Numeric(7, 6), nullable=True),
        sa.Column("slugging_percentage", sa.Numeric(7, 6), nullable=True),
        sa.Column("ops", sa.Numeric(7, 6), nullable=True),
        sa.Column("strikeout_rate", sa.Numeric(7, 6), nullable=True),
        sa.Column("walk_rate", sa.Numeric(7, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "player_id",
            "season_id",
            name="pk_player_season_batting",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["curated.player.player_id"],
            name="fk_player_season_batting_player",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["curated.season.season_id"],
            name="fk_player_season_batting_season",
        ),
        sa.CheckConstraint(
            "games >= 0",
            name="ck_player_season_batting_games",
        ),
        sa.CheckConstraint(
            "plate_appearances >= 0",
            name="ck_player_season_batting_plate_appearances",
        ),
        sa.CheckConstraint(
            "at_bats >= 0",
            name="ck_player_season_batting_at_bats",
        ),
        sa.CheckConstraint(
            "hits >= 0",
            name="ck_player_season_batting_hits",
        ),
        sa.CheckConstraint(
            "singles >= 0",
            name="ck_player_season_batting_singles",
        ),
        sa.CheckConstraint(
            "doubles >= 0",
            name="ck_player_season_batting_doubles",
        ),
        sa.CheckConstraint(
            "triples >= 0",
            name="ck_player_season_batting_triples",
        ),
        sa.CheckConstraint(
            "home_runs >= 0",
            name="ck_player_season_batting_home_runs",
        ),
        sa.CheckConstraint(
            "walks >= 0",
            name="ck_player_season_batting_walks",
        ),
        sa.CheckConstraint(
            "hit_by_pitch >= 0",
            name="ck_player_season_batting_hit_by_pitch",
        ),
        sa.CheckConstraint(
            "strikeouts >= 0",
            name="ck_player_season_batting_strikeouts",
        ),
        sa.CheckConstraint(
            "sacrifice_flies >= 0",
            name="ck_player_season_batting_sacrifice_flies",
        ),
        sa.CheckConstraint(
            "sacrifice_bunts >= 0",
            name="ck_player_season_batting_sacrifice_bunts",
        ),
        sa.CheckConstraint(
            "batting_average IS NULL"
            " OR (batting_average >= 0 AND batting_average <= 1)",
            name="ck_player_season_batting_batting_average",
        ),
        sa.CheckConstraint(
            "on_base_percentage IS NULL"
            " OR (on_base_percentage >= 0 AND on_base_percentage <= 1)",
            name="ck_player_season_batting_on_base_percentage",
        ),
        sa.CheckConstraint(
            "slugging_percentage IS NULL"
            " OR (slugging_percentage >= 0 AND slugging_percentage <= 4)",
            name="ck_player_season_batting_slugging_percentage",
        ),
        sa.CheckConstraint(
            "ops IS NULL OR (ops >= 0 AND ops <= 5)",
            name="ck_player_season_batting_ops",
        ),
        sa.CheckConstraint(
            "strikeout_rate IS NULL"
            " OR (strikeout_rate >= 0 AND strikeout_rate <= 1)",
            name="ck_player_season_batting_strikeout_rate",
        ),
        sa.CheckConstraint(
            "walk_rate IS NULL OR (walk_rate >= 0 AND walk_rate <= 1)",
            name="ck_player_season_batting_walk_rate",
        ),
        schema="analytics",
    )


def downgrade() -> None:
    """Drop analytics.player_season_batting."""
    op.drop_table("player_season_batting", schema="analytics")
