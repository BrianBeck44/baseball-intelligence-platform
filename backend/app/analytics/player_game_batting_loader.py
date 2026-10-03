"""Orchestrate loading analytics player-game batting from curated data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Connection

from app.analytics.player_game_batting_data import (
    get_player_game_batting_appearances,
    load_player_game_batting,
    transform_player_game_batting,
)


@dataclass(frozen=True)
class PlayerGameBattingLoadResult:
    extracted_count: int
    transformed_count: int
    loaded_count: int


def load_player_game_batting_from_curated(
    connection: Connection,
) -> PlayerGameBattingLoadResult:
    """Extract, transform, and insert analytics player-game batting.

    The caller owns the transaction. Exceptions from extraction,
    transformation, or loading are not caught here.
    """
    appearances = get_player_game_batting_appearances(connection)
    rows = transform_player_game_batting(connection, appearances)
    loaded_count = load_player_game_batting(connection, rows)
    return PlayerGameBattingLoadResult(
        extracted_count=len(appearances),
        transformed_count=len(rows),
        loaded_count=loaded_count,
    )
