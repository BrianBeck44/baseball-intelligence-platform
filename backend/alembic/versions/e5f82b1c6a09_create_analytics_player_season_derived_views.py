"""create analytics player-season derived views

Revision ID: e5f82b1c6a09
Revises: d4c91a7e2b08
Create Date: 2026-10-04 17:57:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e5f82b1c6a09"
down_revision: Union[str, Sequence[str], None] = "d4c91a7e2b08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create read-only derived batting and pitching views."""
    op.execute(
        """
        CREATE VIEW analytics.v_player_season_batting_derived AS
        SELECT
            player_id,
            season_id,
            at_bats,
            hits,
            singles,
            doubles,
            triples,
            home_runs,
            (doubles + triples + home_runs) AS extra_base_hits,
            (
                singles
                + (2 * doubles)
                + (3 * triples)
                + (4 * home_runs)
            ) AS total_bases,
            CASE
                WHEN at_bats = 0 THEN NULL
                ELSE CAST(
                    singles
                    + (2 * doubles)
                    + (3 * triples)
                    + (4 * home_runs)
                    - hits
                    AS NUMERIC
                ) / at_bats
            END AS isolated_power
        FROM analytics.player_season_batting
        """
    )
    op.execute(
        """
        CREATE VIEW analytics.v_player_season_pitching_rates AS
        SELECT
            player_id,
            season_id,
            batters_faced,
            walks,
            strikeouts,
            CASE
                WHEN batters_faced = 0 THEN NULL
                ELSE CAST(strikeouts AS NUMERIC) / batters_faced
            END AS strikeout_rate,
            CASE
                WHEN batters_faced = 0 THEN NULL
                ELSE CAST(walks AS NUMERIC) / batters_faced
            END AS walk_rate,
            CASE
                WHEN walks = 0 THEN NULL
                ELSE CAST(strikeouts AS NUMERIC) / walks
            END AS strikeout_to_walk_ratio
        FROM analytics.player_season_pitching
        """
    )


def downgrade() -> None:
    """Drop the derived batting and pitching views."""
    op.execute("DROP VIEW analytics.v_player_season_pitching_rates")
    op.execute("DROP VIEW analytics.v_player_season_batting_derived")
