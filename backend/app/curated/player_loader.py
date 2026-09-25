"""Orchestrate loading curated players from raw Statcast identities."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Connection

from app.curated.player_data import load_mlb_players
from app.curated.statcast_player_ids import get_statcast_player_ids
from app.mlb.stats_api import fetch_mlb_players


@dataclass(frozen=True)
class PlayerLoadResult:
    player_ids_found: int
    players_resolved: int
    players_loaded: int


def load_players_from_statcast(connection: Connection) -> PlayerLoadResult:
    """Resolve Statcast player IDs through the MLB API and upsert them.

    The caller owns the transaction. Exceptions from the API client or
    database loader are not caught here.
    """
    player_ids = get_statcast_player_ids(connection)
    if not player_ids:
        return PlayerLoadResult(
            player_ids_found=0,
            players_resolved=0,
            players_loaded=0,
        )

    players = fetch_mlb_players(player_ids)
    players_loaded = load_mlb_players(connection, players)
    return PlayerLoadResult(
        player_ids_found=len(player_ids),
        players_resolved=len(players),
        players_loaded=players_loaded,
    )
