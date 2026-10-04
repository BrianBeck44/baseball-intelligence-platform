"""create analytics player_pitch_type_effectiveness table

Revision ID: 4ebd18810a99
Revises: e7c91defa856
Create Date: 2026-10-03 19:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4ebd18810a99"
down_revision: Union[str, Sequence[str], None] = "e7c91defa856"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics.player_pitch_type_effectiveness."""
    op.create_table(
        "player_pitch_type_effectiveness",
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("pitch_type_id", sa.Integer(), nullable=False),
        sa.Column("pitches", sa.Integer(), nullable=False),
        sa.Column("plate_appearances", sa.Integer(), nullable=False),
        sa.Column("balls_in_play", sa.Integer(), nullable=False),
        sa.Column("swings", sa.Integer(), nullable=False),
        sa.Column("whiffs", sa.Integer(), nullable=False),
        sa.Column("called_strikes", sa.Integer(), nullable=False),
        sa.Column("fouls", sa.Integer(), nullable=False),
        sa.Column("hits_allowed", sa.Integer(), nullable=False),
        sa.Column("home_runs_allowed", sa.Integer(), nullable=False),
        sa.Column("strikeouts", sa.Integer(), nullable=False),
        sa.Column("walks", sa.Integer(), nullable=False),
        sa.Column("hit_by_pitch", sa.Integer(), nullable=False),
        sa.Column("whiff_rate", sa.Numeric(7, 6), nullable=True),
        sa.Column("called_strike_rate", sa.Numeric(7, 6), nullable=True),
        sa.Column("swing_rate", sa.Numeric(7, 6), nullable=True),
        sa.Column("contact_rate", sa.Numeric(7, 6), nullable=True),
        sa.Column("strikeout_rate", sa.Numeric(7, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "player_id",
            "pitch_type_id",
            name="pk_player_pitch_type_effectiveness",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["curated.player.player_id"],
            name="fk_player_pitch_type_effectiveness_player",
        ),
        sa.ForeignKeyConstraint(
            ["pitch_type_id"],
            ["curated.pitch_type.id"],
            name="fk_player_pitch_type_effectiveness_pitch_type",
        ),
        sa.CheckConstraint(
            "pitches >= 0",
            name="ck_player_pitch_type_effectiveness_pitches",
        ),
        sa.CheckConstraint(
            "plate_appearances >= 0",
            name="ck_player_pitch_type_effectiveness_plate_appearances",
        ),
        sa.CheckConstraint(
            "balls_in_play >= 0",
            name="ck_player_pitch_type_effectiveness_balls_in_play",
        ),
        sa.CheckConstraint(
            "swings >= 0",
            name="ck_player_pitch_type_effectiveness_swings",
        ),
        sa.CheckConstraint(
            "whiffs >= 0",
            name="ck_player_pitch_type_effectiveness_whiffs",
        ),
        sa.CheckConstraint(
            "called_strikes >= 0",
            name="ck_player_pitch_type_effectiveness_called_strikes",
        ),
        sa.CheckConstraint(
            "fouls >= 0",
            name="ck_player_pitch_type_effectiveness_fouls",
        ),
        sa.CheckConstraint(
            "hits_allowed >= 0",
            name="ck_player_pitch_type_effectiveness_hits_allowed",
        ),
        sa.CheckConstraint(
            "home_runs_allowed >= 0",
            name="ck_player_pitch_type_effectiveness_home_runs_allowed",
        ),
        sa.CheckConstraint(
            "strikeouts >= 0",
            name="ck_player_pitch_type_effectiveness_strikeouts",
        ),
        sa.CheckConstraint(
            "walks >= 0",
            name="ck_player_pitch_type_effectiveness_walks",
        ),
        sa.CheckConstraint(
            "hit_by_pitch >= 0",
            name="ck_player_pitch_type_effectiveness_hit_by_pitch",
        ),
        sa.CheckConstraint(
            "whiff_rate IS NULL OR (whiff_rate >= 0 AND whiff_rate <= 1)",
            name="ck_player_pitch_type_effectiveness_whiff_rate",
        ),
        sa.CheckConstraint(
            "called_strike_rate IS NULL"
            " OR (called_strike_rate >= 0 AND called_strike_rate <= 1)",
            name="ck_player_pitch_type_effectiveness_called_strike_rate",
        ),
        sa.CheckConstraint(
            "swing_rate IS NULL OR (swing_rate >= 0 AND swing_rate <= 1)",
            name="ck_player_pitch_type_effectiveness_swing_rate",
        ),
        sa.CheckConstraint(
            "contact_rate IS NULL"
            " OR (contact_rate >= 0 AND contact_rate <= 1)",
            name="ck_player_pitch_type_effectiveness_contact_rate",
        ),
        sa.CheckConstraint(
            "strikeout_rate IS NULL"
            " OR (strikeout_rate >= 0 AND strikeout_rate <= 1)",
            name="ck_player_pitch_type_effectiveness_strikeout_rate",
        ),
        schema="analytics",
    )


def downgrade() -> None:
    """Drop analytics.player_pitch_type_effectiveness."""
    op.drop_table("player_pitch_type_effectiveness", schema="analytics")
