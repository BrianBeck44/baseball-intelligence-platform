"""create analytics player_performance_trends view

Revision ID: f6a93c2d7b10
Revises: e5f82b1c6a09
Create Date: 2026-10-05 16:58:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f6a93c2d7b10"
down_revision: Union[str, Sequence[str], None] = "e5f82b1c6a09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create analytics.player_performance_trends."""
    op.execute(
        """
        CREATE VIEW analytics.player_performance_trends AS
        WITH base_games AS (
            SELECT
                pgb.player_id,
                pgb.game_id,
                pgb.team_id,
                g.season_id,
                g.official_game_date AS game_date,
                pgb.plate_appearances,
                pgb.at_bats,
                pgb.hits,
                pgb.singles,
                pgb.doubles,
                pgb.triples,
                pgb.home_runs,
                pgb.walks,
                pgb.hit_by_pitch,
                pgb.strikeouts,
                pgb.sacrifice_flies,
                pgb.sacrifice_bunts
            FROM analytics.player_game_batting AS pgb
            JOIN curated.game AS g
              ON g.game_id = pgb.game_id
            JOIN curated.season AS s
              ON s.season_id = g.season_id
        ),
        numbered_games AS (
            SELECT
                base_games.*,
                ROW_NUMBER() OVER (
                    PARTITION BY player_id
                    ORDER BY game_date, game_id, team_id
                ) AS player_game_number,
                ROW_NUMBER() OVER (
                    PARTITION BY player_id, season_id
                    ORDER BY game_date, game_id, team_id
                ) AS season_game_number
            FROM base_games
        ),
        rolling_counts AS (
            SELECT
                numbered_games.*,
                SUM(plate_appearances) OVER w7 AS rolling_7_plate_appearances,
                SUM(at_bats) OVER w7 AS rolling_7_at_bats,
                SUM(hits) OVER w7 AS rolling_7_hits,
                SUM(singles) OVER w7 AS rolling_7_singles,
                SUM(doubles) OVER w7 AS rolling_7_doubles,
                SUM(triples) OVER w7 AS rolling_7_triples,
                SUM(home_runs) OVER w7 AS rolling_7_home_runs,
                SUM(walks) OVER w7 AS rolling_7_walks,
                SUM(hit_by_pitch) OVER w7 AS rolling_7_hit_by_pitch,
                SUM(strikeouts) OVER w7 AS rolling_7_strikeouts,
                SUM(sacrifice_flies) OVER w7 AS rolling_7_sacrifice_flies,
                SUM(sacrifice_bunts) OVER w7 AS rolling_7_sacrifice_bunts,
                SUM(plate_appearances) OVER w14
                    AS rolling_14_plate_appearances,
                SUM(at_bats) OVER w14 AS rolling_14_at_bats,
                SUM(hits) OVER w14 AS rolling_14_hits,
                SUM(singles) OVER w14 AS rolling_14_singles,
                SUM(doubles) OVER w14 AS rolling_14_doubles,
                SUM(triples) OVER w14 AS rolling_14_triples,
                SUM(home_runs) OVER w14 AS rolling_14_home_runs,
                SUM(walks) OVER w14 AS rolling_14_walks,
                SUM(hit_by_pitch) OVER w14 AS rolling_14_hit_by_pitch,
                SUM(strikeouts) OVER w14 AS rolling_14_strikeouts,
                SUM(sacrifice_flies) OVER w14
                    AS rolling_14_sacrifice_flies,
                SUM(sacrifice_bunts) OVER w14
                    AS rolling_14_sacrifice_bunts,
                SUM(plate_appearances) OVER w30
                    AS rolling_30_plate_appearances,
                SUM(at_bats) OVER w30 AS rolling_30_at_bats,
                SUM(hits) OVER w30 AS rolling_30_hits,
                SUM(singles) OVER w30 AS rolling_30_singles,
                SUM(doubles) OVER w30 AS rolling_30_doubles,
                SUM(triples) OVER w30 AS rolling_30_triples,
                SUM(home_runs) OVER w30 AS rolling_30_home_runs,
                SUM(walks) OVER w30 AS rolling_30_walks,
                SUM(hit_by_pitch) OVER w30 AS rolling_30_hit_by_pitch,
                SUM(strikeouts) OVER w30 AS rolling_30_strikeouts,
                SUM(sacrifice_flies) OVER w30
                    AS rolling_30_sacrifice_flies,
                SUM(sacrifice_bunts) OVER w30
                    AS rolling_30_sacrifice_bunts
            FROM numbered_games
            WINDOW
                w7 AS (
                    PARTITION BY player_id
                    ORDER BY game_date, game_id, team_id
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ),
                w14 AS (
                    PARTITION BY player_id
                    ORDER BY game_date, game_id, team_id
                    ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
                ),
                w30 AS (
                    PARTITION BY player_id
                    ORDER BY game_date, game_id, team_id
                    ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                )
        ),
        season_counts AS (
            SELECT
                rolling_counts.*,
                SUM(plate_appearances) OVER w_season
                    AS season_plate_appearances,
                SUM(at_bats) OVER w_season AS season_at_bats,
                SUM(hits) OVER w_season AS season_hits,
                SUM(singles) OVER w_season AS season_singles,
                SUM(doubles) OVER w_season AS season_doubles,
                SUM(triples) OVER w_season AS season_triples,
                SUM(home_runs) OVER w_season AS season_home_runs,
                SUM(walks) OVER w_season AS season_walks,
                SUM(hit_by_pitch) OVER w_season AS season_hit_by_pitch,
                SUM(strikeouts) OVER w_season AS season_strikeouts,
                SUM(sacrifice_flies) OVER w_season
                    AS season_sacrifice_flies,
                SUM(sacrifice_bunts) OVER w_season
                    AS season_sacrifice_bunts
            FROM rolling_counts
            WINDOW w_season AS (
                PARTITION BY player_id, season_id
                ORDER BY game_date, game_id, team_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            )
        ),
        final_rates AS (
            SELECT
                season_counts.*,
                CAST(hits AS NUMERIC)
                    / NULLIF(at_bats, 0) AS batting_average,
                CAST(hits + walks + hit_by_pitch AS NUMERIC)
                    / NULLIF(
                        at_bats + walks + hit_by_pitch + sacrifice_flies,
                        0
                    ) AS on_base_percentage,
                CAST(
                    singles
                    + (2 * doubles)
                    + (3 * triples)
                    + (4 * home_runs)
                    AS NUMERIC
                ) / NULLIF(at_bats, 0) AS slugging_percentage,
                CAST(strikeouts AS NUMERIC)
                    / NULLIF(plate_appearances, 0) AS strikeout_rate,
                CAST(walks AS NUMERIC)
                    / NULLIF(plate_appearances, 0) AS walk_rate,
                CAST(rolling_7_hits AS NUMERIC)
                    / NULLIF(rolling_7_at_bats, 0)
                    AS rolling_7_batting_average,
                CAST(
                    rolling_7_hits
                    + rolling_7_walks
                    + rolling_7_hit_by_pitch
                    AS NUMERIC
                ) / NULLIF(
                    rolling_7_at_bats
                    + rolling_7_walks
                    + rolling_7_hit_by_pitch
                    + rolling_7_sacrifice_flies,
                    0
                ) AS rolling_7_on_base_percentage,
                CAST(
                    rolling_7_singles
                    + (2 * rolling_7_doubles)
                    + (3 * rolling_7_triples)
                    + (4 * rolling_7_home_runs)
                    AS NUMERIC
                ) / NULLIF(rolling_7_at_bats, 0)
                    AS rolling_7_slugging_percentage,
                CAST(rolling_7_strikeouts AS NUMERIC)
                    / NULLIF(rolling_7_plate_appearances, 0)
                    AS rolling_7_strikeout_rate,
                CAST(rolling_7_walks AS NUMERIC)
                    / NULLIF(rolling_7_plate_appearances, 0)
                    AS rolling_7_walk_rate,
                CAST(rolling_14_hits AS NUMERIC)
                    / NULLIF(rolling_14_at_bats, 0)
                    AS rolling_14_batting_average,
                CAST(
                    rolling_14_hits
                    + rolling_14_walks
                    + rolling_14_hit_by_pitch
                    AS NUMERIC
                ) / NULLIF(
                    rolling_14_at_bats
                    + rolling_14_walks
                    + rolling_14_hit_by_pitch
                    + rolling_14_sacrifice_flies,
                    0
                ) AS rolling_14_on_base_percentage,
                CAST(
                    rolling_14_singles
                    + (2 * rolling_14_doubles)
                    + (3 * rolling_14_triples)
                    + (4 * rolling_14_home_runs)
                    AS NUMERIC
                ) / NULLIF(rolling_14_at_bats, 0)
                    AS rolling_14_slugging_percentage,
                CAST(rolling_14_strikeouts AS NUMERIC)
                    / NULLIF(rolling_14_plate_appearances, 0)
                    AS rolling_14_strikeout_rate,
                CAST(rolling_14_walks AS NUMERIC)
                    / NULLIF(rolling_14_plate_appearances, 0)
                    AS rolling_14_walk_rate,
                CAST(rolling_30_hits AS NUMERIC)
                    / NULLIF(rolling_30_at_bats, 0)
                    AS rolling_30_batting_average,
                CAST(
                    rolling_30_hits
                    + rolling_30_walks
                    + rolling_30_hit_by_pitch
                    AS NUMERIC
                ) / NULLIF(
                    rolling_30_at_bats
                    + rolling_30_walks
                    + rolling_30_hit_by_pitch
                    + rolling_30_sacrifice_flies,
                    0
                ) AS rolling_30_on_base_percentage,
                CAST(
                    rolling_30_singles
                    + (2 * rolling_30_doubles)
                    + (3 * rolling_30_triples)
                    + (4 * rolling_30_home_runs)
                    AS NUMERIC
                ) / NULLIF(rolling_30_at_bats, 0)
                    AS rolling_30_slugging_percentage,
                CAST(rolling_30_strikeouts AS NUMERIC)
                    / NULLIF(rolling_30_plate_appearances, 0)
                    AS rolling_30_strikeout_rate,
                CAST(rolling_30_walks AS NUMERIC)
                    / NULLIF(rolling_30_plate_appearances, 0)
                    AS rolling_30_walk_rate,
                CAST(season_hits AS NUMERIC)
                    / NULLIF(season_at_bats, 0)
                    AS season_batting_average,
                CAST(
                    season_hits
                    + season_walks
                    + season_hit_by_pitch
                    AS NUMERIC
                ) / NULLIF(
                    season_at_bats
                    + season_walks
                    + season_hit_by_pitch
                    + season_sacrifice_flies,
                    0
                ) AS season_on_base_percentage,
                CAST(
                    season_singles
                    + (2 * season_doubles)
                    + (3 * season_triples)
                    + (4 * season_home_runs)
                    AS NUMERIC
                ) / NULLIF(season_at_bats, 0)
                    AS season_slugging_percentage,
                CAST(season_strikeouts AS NUMERIC)
                    / NULLIF(season_plate_appearances, 0)
                    AS season_strikeout_rate,
                CAST(season_walks AS NUMERIC)
                    / NULLIF(season_plate_appearances, 0)
                    AS season_walk_rate
            FROM season_counts
        )
        SELECT
            player_id,
            game_id,
            team_id,
            season_id,
            game_date,
            player_game_number,
            season_game_number,
            plate_appearances,
            at_bats,
            hits,
            singles,
            doubles,
            triples,
            home_runs,
            walks,
            hit_by_pitch,
            strikeouts,
            sacrifice_flies,
            sacrifice_bunts,
            batting_average,
            on_base_percentage,
            slugging_percentage,
            on_base_percentage + slugging_percentage AS ops,
            strikeout_rate,
            walk_rate,
            rolling_7_plate_appearances,
            rolling_7_at_bats,
            rolling_7_hits,
            rolling_7_singles,
            rolling_7_doubles,
            rolling_7_triples,
            rolling_7_home_runs,
            rolling_7_walks,
            rolling_7_hit_by_pitch,
            rolling_7_strikeouts,
            rolling_7_sacrifice_flies,
            rolling_7_sacrifice_bunts,
            rolling_7_batting_average,
            rolling_7_on_base_percentage,
            rolling_7_slugging_percentage,
            rolling_7_on_base_percentage
                + rolling_7_slugging_percentage AS rolling_7_ops,
            rolling_7_strikeout_rate,
            rolling_7_walk_rate,
            rolling_14_plate_appearances,
            rolling_14_at_bats,
            rolling_14_hits,
            rolling_14_singles,
            rolling_14_doubles,
            rolling_14_triples,
            rolling_14_home_runs,
            rolling_14_walks,
            rolling_14_hit_by_pitch,
            rolling_14_strikeouts,
            rolling_14_sacrifice_flies,
            rolling_14_sacrifice_bunts,
            rolling_14_batting_average,
            rolling_14_on_base_percentage,
            rolling_14_slugging_percentage,
            rolling_14_on_base_percentage
                + rolling_14_slugging_percentage AS rolling_14_ops,
            rolling_14_strikeout_rate,
            rolling_14_walk_rate,
            rolling_30_plate_appearances,
            rolling_30_at_bats,
            rolling_30_hits,
            rolling_30_singles,
            rolling_30_doubles,
            rolling_30_triples,
            rolling_30_home_runs,
            rolling_30_walks,
            rolling_30_hit_by_pitch,
            rolling_30_strikeouts,
            rolling_30_sacrifice_flies,
            rolling_30_sacrifice_bunts,
            rolling_30_batting_average,
            rolling_30_on_base_percentage,
            rolling_30_slugging_percentage,
            rolling_30_on_base_percentage
                + rolling_30_slugging_percentage AS rolling_30_ops,
            rolling_30_strikeout_rate,
            rolling_30_walk_rate,
            season_plate_appearances,
            season_at_bats,
            season_hits,
            season_singles,
            season_doubles,
            season_triples,
            season_home_runs,
            season_walks,
            season_hit_by_pitch,
            season_strikeouts,
            season_sacrifice_flies,
            season_sacrifice_bunts,
            season_batting_average,
            season_on_base_percentage,
            season_slugging_percentage,
            season_on_base_percentage
                + season_slugging_percentage AS season_ops,
            season_strikeout_rate,
            season_walk_rate
        FROM final_rates
        ORDER BY player_id, game_date, game_id, team_id
        """
    )


def downgrade() -> None:
    """Drop analytics.player_performance_trends."""
    op.execute("DROP VIEW analytics.player_performance_trends")
