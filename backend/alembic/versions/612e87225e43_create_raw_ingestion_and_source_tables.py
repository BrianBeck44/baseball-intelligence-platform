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


def downgrade() -> None:
    """Drop raw ingestion and source tables."""
    op.drop_table("team_metadata", schema="raw")
    op.drop_table("player_metadata", schema="raw")
    op.drop_table("game_metadata", schema="raw")
    op.drop_table("ingestion_batch", schema="raw")
