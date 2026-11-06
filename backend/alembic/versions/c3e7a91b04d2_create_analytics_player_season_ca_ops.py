"""create analytics player_season_ca_ops table

Revision ID: c3e7a91b04d2
Revises: e2057fe7e391
Create Date: 2026-10-27 17:28:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3e7a91b04d2"
down_revision: Union[str, Sequence[str], None] = "e2057fe7e391"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics.player_season_ca_ops."""
    op.create_table(
        "player_season_ca_ops",
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("season_id", sa.BigInteger(), nullable=False),
        sa.Column("plate_appearances", sa.Integer(), nullable=False),
        sa.Column("observed_ops", sa.Numeric(7, 6), nullable=True),
        sa.Column("league_ops", sa.Numeric(7, 6), nullable=True),
        sa.Column("expected_opponent_ops", sa.Numeric(7, 6), nullable=True),
        sa.Column("ca_ops", sa.Numeric(8, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "player_id",
            "season_id",
            name="pk_player_season_ca_ops",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["curated.player.player_id"],
            name="fk_player_season_ca_ops_player",
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["curated.season.season_id"],
            name="fk_player_season_ca_ops_season",
        ),
        sa.CheckConstraint(
            "plate_appearances >= 0",
            name="ck_player_season_ca_ops_plate_appearances",
        ),
        sa.CheckConstraint(
            "observed_ops IS NULL OR (observed_ops >= 0 AND observed_ops <= 5)",
            name="ck_player_season_ca_ops_observed_ops",
        ),
        sa.CheckConstraint(
            "league_ops IS NULL OR (league_ops >= 0 AND league_ops <= 5)",
            name="ck_player_season_ca_ops_league_ops",
        ),
        sa.CheckConstraint(
            "expected_opponent_ops IS NULL"
            " OR (expected_opponent_ops >= 0 AND expected_opponent_ops <= 5)",
            name="ck_player_season_ca_ops_expected_opponent_ops",
        ),
        sa.CheckConstraint(
            "ca_ops IS NULL OR (ca_ops >= -5 AND ca_ops <= 10)",
            name="ck_player_season_ca_ops_ca_ops",
        ),
        schema="analytics",
    )


def downgrade() -> None:
    """Drop analytics.player_season_ca_ops."""
    op.drop_table("player_season_ca_ops", schema="analytics")
