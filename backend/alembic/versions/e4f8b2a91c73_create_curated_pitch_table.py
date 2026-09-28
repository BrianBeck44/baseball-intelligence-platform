"""create curated pitch table

Revision ID: e4f8b2a91c73
Revises: d8a1c4f27b90
Create Date: 2026-09-28 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f8b2a91c73"
down_revision: Union[str, Sequence[str], None] = "d8a1c4f27b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create curated.pitch."""
    op.create_table(
        "pitch",
        sa.Column(
            "pitch_id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("plate_appearance_id", sa.BigInteger(), nullable=False),
        sa.Column("pitch_number", sa.Integer(), nullable=False),
        sa.Column("pitch_type_id", sa.Integer(), nullable=True),
        sa.Column("pitch_outcome_type_id", sa.Integer(), nullable=True),
        sa.Column("balls", sa.SmallInteger(), nullable=True),
        sa.Column("strikes", sa.SmallInteger(), nullable=True),
        sa.Column("zone", sa.SmallInteger(), nullable=True),
        sa.Column("plate_x", sa.Double(), nullable=True),
        sa.Column("plate_z", sa.Double(), nullable=True),
        sa.Column("sz_top", sa.Double(), nullable=True),
        sa.Column("sz_bot", sa.Double(), nullable=True),
        sa.Column("release_speed", sa.Double(), nullable=True),
        sa.Column("effective_speed", sa.Double(), nullable=True),
        sa.Column("release_spin", sa.Double(), nullable=True),
        sa.Column("spin_axis", sa.Double(), nullable=True),
        sa.Column("release_pos_x", sa.Double(), nullable=True),
        sa.Column("release_pos_y", sa.Double(), nullable=True),
        sa.Column("release_pos_z", sa.Double(), nullable=True),
        sa.Column("release_extension", sa.Double(), nullable=True),
        sa.Column("pfx_x", sa.Double(), nullable=True),
        sa.Column("pfx_z", sa.Double(), nullable=True),
        sa.Column("vx0", sa.Double(), nullable=True),
        sa.Column("vy0", sa.Double(), nullable=True),
        sa.Column("vz0", sa.Double(), nullable=True),
        sa.Column("ax", sa.Double(), nullable=True),
        sa.Column("ay", sa.Double(), nullable=True),
        sa.Column("az", sa.Double(), nullable=True),
        sa.Column("home_score", sa.SmallInteger(), nullable=True),
        sa.Column("away_score", sa.SmallInteger(), nullable=True),
        sa.Column("post_home_score", sa.SmallInteger(), nullable=True),
        sa.Column("post_away_score", sa.SmallInteger(), nullable=True),
        sa.Column("home_win_exp", sa.Double(), nullable=True),
        sa.Column("bat_win_exp", sa.Double(), nullable=True),
        sa.Column("delta_home_win_exp", sa.Double(), nullable=True),
        sa.Column("delta_run_exp", sa.Double(), nullable=True),
        sa.Column("estimated_ba_using_speedangle", sa.Double(), nullable=True),
        sa.Column("estimated_woba_using_speedangle", sa.Double(), nullable=True),
        sa.Column("woba_value", sa.Double(), nullable=True),
        sa.Column("hc_x", sa.Double(), nullable=True),
        sa.Column("hc_y", sa.Double(), nullable=True),
        sa.Column("hit_distance", sa.Double(), nullable=True),
        sa.Column("launch_speed", sa.Double(), nullable=True),
        sa.Column("launch_angle", sa.Double(), nullable=True),
        sa.Column("hyper_speed", sa.Double(), nullable=True),
        sa.Column("arm_angle", sa.Double(), nullable=True),
        sa.Column("attack_angle", sa.Double(), nullable=True),
        sa.Column("attack_direction", sa.Double(), nullable=True),
        sa.Column("swing_path_tilt", sa.Double(), nullable=True),
        sa.Column(
            "intercept_ball_minus_batter_pos_x_inches",
            sa.Double(),
            nullable=True,
        ),
        sa.Column(
            "intercept_ball_minus_batter_pos_y_inches",
            sa.Double(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("pitch_id", name="pk_pitch"),
        sa.UniqueConstraint(
            "plate_appearance_id",
            "pitch_number",
            name="uq_pitch_plate_appearance_pitch_number",
        ),
        sa.ForeignKeyConstraint(
            ["plate_appearance_id"],
            ["curated.plate_appearance.plate_appearance_id"],
            name="fk_pitch_plate_appearance",
        ),
        sa.ForeignKeyConstraint(
            ["pitch_type_id"],
            ["curated.pitch_type.id"],
            name="fk_pitch_pitch_type",
        ),
        sa.ForeignKeyConstraint(
            ["pitch_outcome_type_id"],
            ["curated.pitch_outcome_type.id"],
            name="fk_pitch_pitch_outcome_type",
        ),
        sa.CheckConstraint(
            "pitch_number > 0",
            name="ck_pitch_pitch_number_positive",
        ),
        sa.CheckConstraint(
            "balls IS NULL OR balls BETWEEN 0 AND 3",
            name="ck_pitch_balls",
        ),
        sa.CheckConstraint(
            "strikes IS NULL OR strikes BETWEEN 0 AND 2",
            name="ck_pitch_strikes",
        ),
        sa.CheckConstraint(
            "zone IS NULL OR zone BETWEEN 1 AND 14",
            name="ck_pitch_zone",
        ),
        schema="curated",
    )
    op.create_index(
        "idx_pitch_plate_appearance_id",
        "pitch",
        ["plate_appearance_id"],
        schema="curated",
    )
    op.create_index(
        "idx_pitch_pitch_type_id",
        "pitch",
        ["pitch_type_id"],
        schema="curated",
    )
    op.create_index(
        "idx_pitch_pitch_outcome_type_id",
        "pitch",
        ["pitch_outcome_type_id"],
        schema="curated",
    )


def downgrade() -> None:
    """Drop curated.pitch."""
    op.drop_index(
        "idx_pitch_pitch_outcome_type_id",
        table_name="pitch",
        schema="curated",
    )
    op.drop_index(
        "idx_pitch_pitch_type_id",
        table_name="pitch",
        schema="curated",
    )
    op.drop_index(
        "idx_pitch_plate_appearance_id",
        table_name="pitch",
        schema="curated",
    )
    op.drop_table("pitch", schema="curated")
