"""Coordinate season-wide CA-OPS analytics retrieval."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.analytics.player_season_batting_lookup import get_season
from app.analytics.player_season_ca_ops_lookup import (
    list_player_season_ca_ops_for_season,
)
from app.api.schemas import (
    PlayerSeasonCaOpsResponse,
    SeasonCaOpsAnalyticsResponse,
)


def get_season_ca_ops_analytics_response(
    connection: Connection,
    *,
    season_id: int,
) -> SeasonCaOpsAnalyticsResponse:
    """Return stored CA-OPS lines for every player in one season.

    Rows are read from ``analytics.player_season_ca_ops``. CA-OPS is
    not recomputed. An unknown or empty season returns 200 with an
    empty player list. ``season_year`` is null when the season itself
    does not exist. The caller owns the transaction.
    """
    season = get_season(connection, season_id)
    rows = list_player_season_ca_ops_for_season(
        connection,
        season_id=season_id,
    )
    season_year = None if season is None else season.season_year
    return SeasonCaOpsAnalyticsResponse(
        season_id=season_id,
        season_year=season_year,
        players=[
            PlayerSeasonCaOpsResponse(
                player_id=row.player_id,
                full_name=row.full_name,
                season_id=row.season_id,
                season_year=season_year,
                plate_appearances=row.plate_appearances,
                observed_ops=row.observed_ops,
                league_ops=row.league_ops,
                expected_opponent_ops=row.expected_opponent_ops,
                ca_ops=row.ca_ops,
            )
            for row in rows
        ],
    )
