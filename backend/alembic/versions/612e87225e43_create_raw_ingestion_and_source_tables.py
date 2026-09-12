"""create raw ingestion and source tables

Revision ID: 612e87225e43
Revises: a971abe56ffc
Create Date: 2026-09-12 12:54:41.652828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "612e87225e43"
down_revision: Union[str, Sequence[str], None] = "a971abe56ffc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create raw ingestion and source tables."""
    op.create_table(
        "ingestion_batch",
        sa.Column(
            "ingestion_batch_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("records_received", sa.Integer(), nullable=True),
        sa.Column("records_loaded", sa.Integer(), nullable=True),
        sa.Column("records_rejected", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("ingestion_batch_id", name="pk_ingestion_batch"),
        sa.CheckConstraint(
            "records_received IS NULL OR records_received >= 0",
            name="ck_ingestion_batch_records_received",
        ),
        sa.CheckConstraint(
            "records_loaded IS NULL OR records_loaded >= 0",
            name="ck_ingestion_batch_records_loaded",
        ),
        sa.CheckConstraint(
            "records_rejected IS NULL OR records_rejected >= 0",
            name="ck_ingestion_batch_records_rejected",
        ),
        schema="raw",
    )

    op.create_table(
        "game_metadata",
        sa.Column(
            "raw_game_metadata_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("game_pk", sa.BigInteger(), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=True),
        sa.Column("game_type", sa.Text(), nullable=True),
        sa.Column("home_team_id", sa.BigInteger(), nullable=True),
        sa.Column("home_team_abbreviation", sa.Text(), nullable=True),
        sa.Column("away_team_id", sa.BigInteger(), nullable=True),
        sa.Column("away_team_abbreviation", sa.Text(), nullable=True),
        sa.Column("venue_id", sa.BigInteger(), nullable=True),
        sa.Column("venue_name", sa.Text(), nullable=True),
        sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("game_status", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("raw_game_metadata_id", name="pk_game_metadata"),
        sa.UniqueConstraint(
            "source_name",
            "game_pk",
            name="uq_game_metadata_source_name_game_pk",
        ),
        schema="raw",
    )

    op.create_table(
        "player_metadata",
        sa.Column(
            "raw_player_metadata_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("mlbam_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("birth_country", sa.Text(), nullable=True),
        sa.Column("height", sa.Text(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("bat_side", sa.Text(), nullable=True),
        sa.Column("pitch_hand", sa.Text(), nullable=True),
        sa.Column("mlb_debut_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("raw_player_metadata_id", name="pk_player_metadata"),
        sa.UniqueConstraint(
            "source_name",
            "mlbam_id",
            name="uq_player_metadata_source_name_mlbam_id",
        ),
        schema="raw",
    )

    op.create_table(
        "team_metadata",
        sa.Column(
            "raw_team_metadata_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("mlbam_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("abbreviation", sa.Text(), nullable=True),
        sa.Column("location_name", sa.Text(), nullable=True),
        sa.Column("first_year_of_play", sa.SmallInteger(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("raw_team_metadata_id", name="pk_team_metadata"),
        sa.UniqueConstraint(
            "source_name",
            "mlbam_id",
            name="uq_team_metadata_source_name_mlbam_id",
        ),
        schema="raw",
    )

    op.create_table(
        "statcast_pitch",
        sa.Column(
            "raw_statcast_pitch_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("game_pk", sa.BigInteger(), nullable=False),
        sa.Column("at_bat_number", sa.Integer(), nullable=False),
        sa.Column("pitch_number", sa.Integer(), nullable=False),
        sa.Column("sv_id", sa.Text(), nullable=True),
        sa.Column("game_date", sa.Date(), nullable=True),
        sa.Column("game_year", sa.Integer(), nullable=True),
        sa.Column("game_type", sa.Text(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=True),
        sa.Column("batter", sa.BigInteger(), nullable=True),
        sa.Column("pitcher", sa.BigInteger(), nullable=True),
        sa.Column("home_team", sa.Text(), nullable=True),
        sa.Column("away_team", sa.Text(), nullable=True),
        sa.Column("fielder_2", sa.BigInteger(), nullable=True),
        sa.Column("fielder_3", sa.BigInteger(), nullable=True),
        sa.Column("fielder_4", sa.BigInteger(), nullable=True),
        sa.Column("fielder_5", sa.BigInteger(), nullable=True),
        sa.Column("fielder_6", sa.BigInteger(), nullable=True),
        sa.Column("fielder_7", sa.BigInteger(), nullable=True),
        sa.Column("fielder_8", sa.BigInteger(), nullable=True),
        sa.Column("fielder_9", sa.BigInteger(), nullable=True),
        sa.Column("pitch_type", sa.Text(), nullable=True),
        sa.Column("pitch_name", sa.Text(), nullable=True),
        sa.Column("events", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("des", sa.Text(), nullable=True),
        sa.Column("zone", sa.Integer(), nullable=True),
        sa.Column("balls", sa.Integer(), nullable=True),
        sa.Column("strikes", sa.Integer(), nullable=True),
        sa.Column("outs_when_up", sa.Integer(), nullable=True),
        sa.Column("inning", sa.Integer(), nullable=True),
        sa.Column("inning_topbot", sa.Text(), nullable=True),
        sa.Column("stand", sa.Text(), nullable=True),
        sa.Column("p_throws", sa.Text(), nullable=True),
        sa.Column("hit_location", sa.Integer(), nullable=True),
        sa.Column("bb_type", sa.Text(), nullable=True),
        sa.Column("on_1b", sa.BigInteger(), nullable=True),
        sa.Column("on_2b", sa.BigInteger(), nullable=True),
        sa.Column("on_3b", sa.BigInteger(), nullable=True),
        sa.Column("release_speed", sa.Double(), nullable=True),
        sa.Column("release_pos_x", sa.Double(), nullable=True),
        sa.Column("release_pos_y", sa.Double(), nullable=True),
        sa.Column("release_pos_z", sa.Double(), nullable=True),
        sa.Column("pfx_x", sa.Double(), nullable=True),
        sa.Column("pfx_z", sa.Double(), nullable=True),
        sa.Column("vx0", sa.Double(), nullable=True),
        sa.Column("vy0", sa.Double(), nullable=True),
        sa.Column("vz0", sa.Double(), nullable=True),
        sa.Column("ax", sa.Double(), nullable=True),
        sa.Column("ay", sa.Double(), nullable=True),
        sa.Column("az", sa.Double(), nullable=True),
        sa.Column("effective_speed", sa.Double(), nullable=True),
        sa.Column("release_spin", sa.Double(), nullable=True),
        sa.Column("release_extension", sa.Double(), nullable=True),
        sa.Column("spin_axis", sa.Double(), nullable=True),
        sa.Column("api_break_z_with_gravity", sa.Double(), nullable=True),
        sa.Column("api_break_x_arm", sa.Double(), nullable=True),
        sa.Column("api_break_x_batter_in", sa.Double(), nullable=True),
        sa.Column("plate_x", sa.Double(), nullable=True),
        sa.Column("plate_z", sa.Double(), nullable=True),
        sa.Column("sz_top", sa.Double(), nullable=True),
        sa.Column("sz_bot", sa.Double(), nullable=True),
        sa.Column("hc_x", sa.Double(), nullable=True),
        sa.Column("hc_y", sa.Double(), nullable=True),
        sa.Column("hit_distance", sa.Double(), nullable=True),
        sa.Column("launch_speed", sa.Double(), nullable=True),
        sa.Column("launch_angle", sa.Double(), nullable=True),
        sa.Column("hyper_speed", sa.Double(), nullable=True),
        sa.Column("launch_speed_angle", sa.Integer(), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("bat_score", sa.Integer(), nullable=True),
        sa.Column("fld_score", sa.Integer(), nullable=True),
        sa.Column("post_home_score", sa.Integer(), nullable=True),
        sa.Column("post_away_score", sa.Integer(), nullable=True),
        sa.Column("post_bat_score", sa.Integer(), nullable=True),
        sa.Column("post_fld_score", sa.Integer(), nullable=True),
        sa.Column("home_score_diff", sa.Integer(), nullable=True),
        sa.Column("bat_score_diff", sa.Integer(), nullable=True),
        sa.Column("home_win_exp", sa.Double(), nullable=True),
        sa.Column("bat_win_exp", sa.Double(), nullable=True),
        sa.Column("delta_home_win_exp", sa.Double(), nullable=True),
        sa.Column("delta_run_exp", sa.Double(), nullable=True),
        sa.Column("estimated_ba_using_speedangle", sa.Double(), nullable=True),
        sa.Column("estimated_woba_using_speedangle", sa.Double(), nullable=True),
        sa.Column("woba_value", sa.Double(), nullable=True),
        sa.Column("woba_denom", sa.Double(), nullable=True),
        sa.Column("babip_value", sa.Double(), nullable=True),
        sa.Column("iso_value", sa.Double(), nullable=True),
        sa.Column("if_fielding_alignment", sa.Text(), nullable=True),
        sa.Column("of_fielding_alignment", sa.Text(), nullable=True),
        sa.Column("age_pit", sa.Integer(), nullable=True),
        sa.Column("age_bat", sa.Integer(), nullable=True),
        sa.Column("n_thruorder_pitcher", sa.Integer(), nullable=True),
        sa.Column("n_priorpa_thisgame_player_at_bat", sa.Integer(), nullable=True),
        sa.Column("pitcher_days_since_prev_game", sa.Integer(), nullable=True),
        sa.Column("batter_days_since_prev_game", sa.Integer(), nullable=True),
        sa.Column("pitcher_days_until_next_game", sa.Integer(), nullable=True),
        sa.Column("batter_days_until_next_game", sa.Integer(), nullable=True),
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
            name="pk_statcast_pitch",
        ),
        sa.UniqueConstraint(
            "game_pk",
            "at_bat_number",
            "pitch_number",
            name="uq_statcast_pitch_game_pk_at_bat_number_pitch_number",
        ),
        sa.CheckConstraint(
            "at_bat_number > 0",
            name="ck_statcast_pitch_at_bat_number_positive",
        ),
        sa.CheckConstraint(
            "pitch_number > 0",
            name="ck_statcast_pitch_pitch_number_positive",
        ),
        schema="raw",
    )


def downgrade() -> None:
    """Drop raw ingestion and source tables."""
    op.drop_table("statcast_pitch", schema="raw")
    op.drop_table("team_metadata", schema="raw")
    op.drop_table("player_metadata", schema="raw")
    op.drop_table("game_metadata", schema="raw")
    op.drop_table("ingestion_batch", schema="raw")
