"""Orchestrate rebuilding analytics tables from curated data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.analytics.player_game_batting_loader import (
    PlayerGameBattingLoadResult,
    load_player_game_batting_from_curated,
)
from app.analytics.player_game_pitching_loader import (
    PlayerGamePitchingLoadResult,
    load_player_game_pitching_from_curated,
)
from app.analytics.player_pitch_type_effectiveness_loader import (
    PlayerPitchTypeEffectivenessLoadResult,
    load_player_pitch_type_effectiveness_from_curated,
)
from app.analytics.player_season_batting_data import (
    get_player_season_batting_games,
    transform_player_season_batting,
)
from app.analytics.player_season_batting_loader import load_player_season_batting
from app.analytics.player_season_pitching_data import (
    get_player_season_pitching_games,
    transform_player_season_pitching,
)
from app.analytics.player_season_pitching_loader import load_player_season_pitching


_ANALYTICS_CLEAR_ORDER = (
    "player_season_batting",
    "player_season_pitching",
    "player_game_batting",
    "player_game_pitching",
    "player_pitch_type_effectiveness",
)


@dataclass(frozen=True)
class SeasonLoadResult:
    extracted_count: int
    transformed_count: int
    loaded_count: int


@dataclass(frozen=True)
class AnalyticsLoadResult:
    game_batting: PlayerGameBattingLoadResult
    game_pitching: PlayerGamePitchingLoadResult
    pitch_type_effectiveness: PlayerPitchTypeEffectivenessLoadResult
    season_batting: SeasonLoadResult
    season_pitching: SeasonLoadResult


def clear_analytics_tables(connection: Connection) -> None:
    """Delete analytics fact rows in reverse dependency order.

    Table definitions, constraints, indexes, and views are left
    unchanged. The caller owns the transaction.
    """
    for table_name in _ANALYTICS_CLEAR_ORDER:
        connection.execute(text(f"DELETE FROM analytics.{table_name}"))


def load_all_analytics(connection: Connection) -> AnalyticsLoadResult:
    """Replace analytics tables from the current curated dataset.

    Existing analytics rows are cleared, then game-level tables are
    loaded before season rollups. The caller owns the transaction.
    Exceptions from any loader are not caught here.
    """
    clear_analytics_tables(connection)

    game_batting = load_player_game_batting_from_curated(connection)
    game_pitching = load_player_game_pitching_from_curated(connection)
    pitch_type_effectiveness = load_player_pitch_type_effectiveness_from_curated(
        connection
    )

    season_batting_games = get_player_season_batting_games(connection)
    season_batting_rows = transform_player_season_batting(
        connection,
        season_batting_games,
    )
    season_batting = SeasonLoadResult(
        extracted_count=len(season_batting_games),
        transformed_count=len(season_batting_rows),
        loaded_count=load_player_season_batting(connection, season_batting_rows),
    )

    season_pitching_games = get_player_season_pitching_games(connection)
    season_pitching_rows = transform_player_season_pitching(
        connection,
        season_pitching_games,
    )
    season_pitching = SeasonLoadResult(
        extracted_count=len(season_pitching_games),
        transformed_count=len(season_pitching_rows),
        loaded_count=load_player_season_pitching(
            connection,
            season_pitching_rows,
        ),
    )

    return AnalyticsLoadResult(
        game_batting=game_batting,
        game_pitching=game_pitching,
        pitch_type_effectiveness=pitch_type_effectiveness,
        season_batting=season_batting,
        season_pitching=season_pitching,
    )
