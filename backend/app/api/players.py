"""Player performance history routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.engine import Connection

from app.api.schemas import PlayerGameHistoryResponse, PlayerListResponse
from app.core.db import get_connection
from app.services.lookups import get_players_for_season
from app.services.player_games import PlayerNotFoundError, get_player_game_history

router = APIRouter(prefix="/players", tags=["players"])

_DEFAULT_GAME_LIMIT = 50
_MAX_GAME_LIMIT = 200


@router.get("", response_model=PlayerListResponse)
def read_players(
    season_id: Annotated[int, Query(ge=1)],
    connection: Annotated[Connection, Depends(get_connection)],
    team_id: Annotated[int | None, Query(ge=1)] = None,
) -> PlayerListResponse:
    """Return distinct batters for one season, optionally filtered by team."""
    return get_players_for_season(
        connection,
        season_id=season_id,
        team_id=team_id,
    )


@router.get("/{player_id}/games", response_model=PlayerGameHistoryResponse)
def read_player_games(
    player_id: Annotated[int, Path(ge=1)],
    season_id: Annotated[int, Query(ge=1)],
    connection: Annotated[Connection, Depends(get_connection)],
    limit: Annotated[
        int,
        Query(ge=1, le=_MAX_GAME_LIMIT),
    ] = _DEFAULT_GAME_LIMIT,
) -> PlayerGameHistoryResponse:
    """Return a player's game-by-game batting history for one season."""
    try:
        return get_player_game_history(
            connection,
            player_id=player_id,
            season_id=season_id,
            limit=limit,
        )
    except PlayerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        ) from exc
