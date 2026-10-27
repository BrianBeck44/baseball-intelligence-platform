"""Coordinate player existence checks and season-batting retrieval."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.analytics.player_performance_trends_data import get_player
from app.analytics.player_season_batting_lookup import (
    get_player_season_batting,
    get_season,
)
from app.api.schemas import PlayerSeasonBattingResponse
from app.services.player_games import PlayerNotFoundError


def get_player_season_batting_response(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
) -> PlayerSeasonBattingResponse:
    """Return one player's season batting line, or raise if unknown.

    A known player with no ``analytics.player_season_batting`` row for
    the requested season returns 200 with identity fields populated and
    batting statistics set to null. That matches ``GET /players/{id}/games``,
    which returns an empty ``games`` list instead of 404. ``season_year``
    is null when the season itself does not exist. The caller owns the
    transaction.
    """
    player = get_player(connection, player_id)
    if player is None:
        raise PlayerNotFoundError(f"Player {player_id} was not found.")

    season = get_season(connection, season_id)
    batting = get_player_season_batting(
        connection,
        player_id=player_id,
        season_id=season_id,
    )
    if batting is None:
        return PlayerSeasonBattingResponse(
            player_id=player.player_id,
            full_name=player.full_name,
            season_id=season_id,
            season_year=None if season is None else season.season_year,
            games=None,
            plate_appearances=None,
            at_bats=None,
            hits=None,
            singles=None,
            doubles=None,
            triples=None,
            home_runs=None,
            walks=None,
            hit_by_pitch=None,
            strikeouts=None,
            sacrifice_flies=None,
            sacrifice_bunts=None,
            batting_average=None,
            on_base_percentage=None,
            slugging_percentage=None,
            ops=None,
            strikeout_rate=None,
            walk_rate=None,
        )

    return PlayerSeasonBattingResponse(
        player_id=player.player_id,
        full_name=player.full_name,
        season_id=batting.season_id,
        season_year=None if season is None else season.season_year,
        games=batting.games,
        plate_appearances=batting.plate_appearances,
        at_bats=batting.at_bats,
        hits=batting.hits,
        singles=batting.singles,
        doubles=batting.doubles,
        triples=batting.triples,
        home_runs=batting.home_runs,
        walks=batting.walks,
        hit_by_pitch=batting.hit_by_pitch,
        strikeouts=batting.strikeouts,
        sacrifice_flies=batting.sacrifice_flies,
        sacrifice_bunts=batting.sacrifice_bunts,
        batting_average=batting.batting_average,
        on_base_percentage=batting.on_base_percentage,
        slugging_percentage=batting.slugging_percentage,
        ops=batting.ops,
        strikeout_rate=batting.strikeout_rate,
        walk_rate=batting.walk_rate,
    )
