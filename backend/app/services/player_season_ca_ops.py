"""Coordinate player existence checks and season CA-OPS retrieval."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.analytics.player_performance_trends_data import get_player
from app.analytics.player_season_batting_lookup import get_season
from app.analytics.player_season_ca_ops_lookup import get_player_season_ca_ops
from app.api.schemas import PlayerSeasonCaOpsResponse
from app.services.player_games import PlayerNotFoundError


def get_player_season_ca_ops_response(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
) -> PlayerSeasonCaOpsResponse:
    """Return one player's season CA-OPS line, or raise if unknown.

    A known player with no ``analytics.player_season_ca_ops`` row for
    the requested season returns 200 with identity fields populated and
    CA-OPS statistics set to null. That matches
    ``GET /players/{id}/season-batting``. ``season_year`` is null when
    the season itself does not exist. The caller owns the transaction.
    """
    player = get_player(connection, player_id)
    if player is None:
        raise PlayerNotFoundError(f"Player {player_id} was not found.")

    season = get_season(connection, season_id)
    ca_ops = get_player_season_ca_ops(
        connection,
        player_id=player_id,
        season_id=season_id,
    )
    if ca_ops is None:
        return PlayerSeasonCaOpsResponse(
            player_id=player.player_id,
            full_name=player.full_name,
            season_id=season_id,
            season_year=None if season is None else season.season_year,
            plate_appearances=None,
            observed_ops=None,
            league_ops=None,
            expected_opponent_ops=None,
            ca_ops=None,
        )

    return PlayerSeasonCaOpsResponse(
        player_id=player.player_id,
        full_name=player.full_name,
        season_id=ca_ops.season_id,
        season_year=None if season is None else season.season_year,
        plate_appearances=ca_ops.plate_appearances,
        observed_ops=ca_ops.observed_ops,
        league_ops=ca_ops.league_ops,
        expected_opponent_ops=ca_ops.expected_opponent_ops,
        ca_ops=ca_ops.ca_ops,
    )
