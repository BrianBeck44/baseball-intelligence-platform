"""create raw statcast pitch table

Revision ID: 20388e16a800
Revises: 612e87225e43
Create Date: 2026-09-15 17:19:50.711489

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20388e16a800"
down_revision: Union[str, Sequence[str], None] = "612e87225e43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "statcast_pitch",
        sa.Column(
            "raw_statcast_pitch_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column(
            "ingestion_batch_id",
            sa.BigInteger(),
            nullable=False,
        ),

        # Source identifiers
        sa.Column("game_pk", sa.BigInteger(), nullable=False),
        sa.Column("at_bat_number", sa.Integer(), nullable=False),
        sa.Column("pitch_number", sa.SmallInteger(), nullable=False),

        # Pitch information
        sa.Column("pitch_type", sa.Text(), nullable=True),
        sa.Column("game_date", sa.Date(), nullable=True),
        sa.Column("release_speed", sa.Double(), nullable=True),
        sa.Column("release_pos_x", sa.Double(), nullable=True),
        sa.Column("release_pos_z", sa.Double(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=True),
        sa.Column("batter", sa.BigInteger(), nullable=True),
        sa.Column("pitcher", sa.BigInteger(), nullable=True),
        sa.Column("events", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("spin_dir", sa.Double(), nullable=True),
        sa.Column("spin_rate_deprecated", sa.Double(), nullable=True),
        sa.Column("break_angle_deprecated", sa.Double(), nullable=True),
        sa.Column("break_length_deprecated", sa.Double(), nullable=True),
        sa.Column("zone", sa.SmallInteger(), nullable=True),
        sa.Column("des", sa.Text(), nullable=True),
        sa.Column("game_type", sa.Text(), nullable=True),
        sa.Column("stand", sa.Text(), nullable=True),
        sa.Column("p_throws", sa.Text(), nullable=True),
        sa.Column("home_team", sa.Text(), nullable=True),
        sa.Column("away_team", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("hit_location", sa.SmallInteger(), nullable=True),
        sa.Column("bb_type", sa.Text(), nullable=True),
        sa.Column("balls", sa.SmallInteger(), nullable=True),
        sa.Column("strikes", sa.SmallInteger(), nullable=True),
        sa.Column("game_year", sa.SmallInteger(), nullable=True),

        # Pitch movement / location
        sa.Column("pfx_x", sa.Double(), nullable=True),
        sa.Column("pfx_z", sa.Double(), nullable=True),
        sa.Column("plate_x", sa.Double(), nullable=True),
        sa.Column("plate_z", sa.Double(), nullable=True),

        # Base runners / game state
        sa.Column("on_3b", sa.BigInteger(), nullable=True),
        sa.Column("on_2b", sa.BigInteger(), nullable=True),
        sa.Column("on_1b", sa.BigInteger(), nullable=True),
        sa.Column("outs_when_up", sa.SmallInteger(), nullable=True),
        sa.Column("inning", sa.SmallInteger(), nullable=True),
        sa.Column("inning_topbot", sa.Text(), nullable=True),

        # Batted-ball location
        sa.Column("hc_x", sa.Double(), nullable=True),
        sa.Column("hc_y", sa.Double(), nullable=True),

        # Deprecated timestamp fields
        sa.Column("tfs_deprecated", sa.Text(), nullable=True),
        sa.Column("tfs_zulu_deprecated", sa.Text(), nullable=True),

        # Source metadata
        sa.Column("umpire", sa.BigInteger(), nullable=True),
        sa.Column("sv_id", sa.Text(), nullable=True),

        # Ball velocity / acceleration
        sa.Column("vx0", sa.Double(), nullable=True),
        sa.Column("vy0", sa.Double(), nullable=True),
        sa.Column("vz0", sa.Double(), nullable=True),
        sa.Column("ax", sa.Double(), nullable=True),
        sa.Column("ay", sa.Double(), nullable=True),
        sa.Column("az", sa.Double(), nullable=True),

        # Strike zone
        sa.Column("sz_top", sa.Double(), nullable=True),
        sa.Column("sz_bot", sa.Double(), nullable=True),

        # Batted-ball measurements
        sa.Column("hit_distance_sc", sa.Double(), nullable=True),
        sa.Column("launch_speed", sa.Double(), nullable=True),
        sa.Column("launch_angle", sa.Double(), nullable=True),

        # Release information
        sa.Column("effective_speed", sa.Double(), nullable=True),
        sa.Column("release_spin_rate", sa.Double(), nullable=True),
        sa.Column("release_extension", sa.Double(), nullable=True),

        # Fielders
        sa.Column("fielder_2", sa.BigInteger(), nullable=True),
        sa.Column("fielder_3", sa.BigInteger(), nullable=True),
        sa.Column("fielder_4", sa.BigInteger(), nullable=True),
        sa.Column("fielder_5", sa.BigInteger(), nullable=True),
        sa.Column("fielder_6", sa.BigInteger(), nullable=True),
        sa.Column("fielder_7", sa.BigInteger(), nullable=True),
        sa.Column("fielder_8", sa.BigInteger(), nullable=True),
        sa.Column("fielder_9", sa.BigInteger(), nullable=True),

        sa.Column("release_pos_y", sa.Double(), nullable=True),

        # Statcast estimated metrics
        sa.Column(
            "estimated_ba_using_speedangle",
            sa.Double(),
            nullable=True,
        ),
        sa.Column(
            "estimated_woba_using_speedangle",
            sa.Double(),
            nullable=True,
        ),
        sa.Column("woba_value", sa.Double(), nullable=True),
        sa.Column("woba_denom", sa.Double(), nullable=True),
        sa.Column("babip_value", sa.Double(), nullable=True),
        sa.Column("iso_value", sa.Double(), nullable=True),
        sa.Column("launch_speed_angle", sa.SmallInteger(), nullable=True),

        # Pitch sequence / scoring
        sa.Column("pitch_name", sa.Text(), nullable=True),
        sa.Column("home_score", sa.SmallInteger(), nullable=True),
        sa.Column("away_score", sa.SmallInteger(), nullable=True),
        sa.Column("bat_score", sa.SmallInteger(), nullable=True),
        sa.Column("fld_score", sa.SmallInteger(), nullable=True),
        sa.Column("post_away_score", sa.SmallInteger(), nullable=True),
        sa.Column("post_home_score", sa.SmallInteger(), nullable=True),
        sa.Column("post_bat_score", sa.SmallInteger(), nullable=True),
        sa.Column("post_fld_score", sa.SmallInteger(), nullable=True),

        # Fielding alignment
        sa.Column("if_fielding_alignment", sa.Text(), nullable=True),
        sa.Column("of_fielding_alignment", sa.Text(), nullable=True),

        # Spin / run expectancy
        sa.Column("spin_axis", sa.Double(), nullable=True),
        sa.Column("delta_home_win_exp", sa.Double(), nullable=True),
        sa.Column("delta_run_exp", sa.Double(), nullable=True),

        # Bat tracking
        sa.Column("bat_speed", sa.Double(), nullable=True),
        sa.Column("swing_length", sa.Double(), nullable=True),
        sa.Column("miss_distance", sa.Double(), nullable=True),

        sa.Column(
            "estimated_slg_using_speedangle",
            sa.Double(),
            nullable=True,
        ),
        sa.Column("delta_pitcher_run_exp", sa.Double(), nullable=True),
        sa.Column("hyper_speed", sa.Double(), nullable=True),

        # Score / win expectancy
        sa.Column("home_score_diff", sa.SmallInteger(), nullable=True),
        sa.Column("bat_score_diff", sa.SmallInteger(), nullable=True),
        sa.Column("home_win_exp", sa.Double(), nullable=True),
        sa.Column("bat_win_exp", sa.Double(), nullable=True),

        # Age
        sa.Column("age_pit_legacy", sa.Double(), nullable=True),
        sa.Column("age_bat_legacy", sa.Double(), nullable=True),
        sa.Column("age_pit", sa.Double(), nullable=True),
        sa.Column("age_bat", sa.Double(), nullable=True),

        # Pitcher / batter usage
        sa.Column("n_thruorder_pitcher", sa.SmallInteger(), nullable=True),
        sa.Column(
            "n_priorpa_thisgame_player_at_bat",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "pitcher_days_since_prev_game",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "batter_days_since_prev_game",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "pitcher_days_until_next_game",
            sa.SmallInteger(),
            nullable=True,
        ),
        sa.Column(
            "batter_days_until_next_game",
            sa.SmallInteger(),
            nullable=True,
        ),

        # API break measurements
        sa.Column("api_break_z_with_gravity", sa.Double(), nullable=True),
        sa.Column("api_break_x_arm", sa.Double(), nullable=True),
        sa.Column("api_break_x_batter_in", sa.Double(), nullable=True),

        # Bat tracking / swing measurements
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

        sa.PrimaryKeyConstraint(
            "raw_statcast_pitch_id",
            name="pk_raw_statcast_pitch",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["raw.ingestion_batch.ingestion_batch_id"],
            name="fk_raw_statcast_pitch_ingestion_batch",
        ),
        sa.UniqueConstraint(
            "game_pk",
            "at_bat_number",
            "pitch_number",
            name="uq_raw_statcast_pitch_source_key",
        ),
        schema="raw",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("statcast_pitch", schema="raw")