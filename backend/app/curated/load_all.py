"""Orchestrate loading curated baseball entities in dependency order."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Connection

from app.curated.game_data import GameLoadResult
from app.curated.game_loader import load_games_from_statcast
from app.curated.game_player_data import GamePlayerLoadResult
from app.curated.game_player_loader import load_game_players_from_statcast
from app.curated.game_team_data import GameTeamLoadResult
from app.curated.game_team_loader import load_game_teams_from_statcast
from app.curated.pitch_loader import (
    PitchLoadOrchestrationResult,
    load_pitches_from_statcast,
)
from app.curated.plate_appearance_loader import (
    PlateAppearanceLoadOrchestrationResult,
    load_plate_appearances_from_statcast,
)
from app.curated.season_data import SeasonLoadResult
from app.curated.season_loader import load_mlb_seasons


@dataclass(frozen=True)
class CuratedLoadResult:
    seasons: SeasonLoadResult
    games: GameLoadResult
    game_teams: GameTeamLoadResult
    game_players: GamePlayerLoadResult
    plate_appearances: PlateAppearanceLoadOrchestrationResult
    pitches: PitchLoadOrchestrationResult


def load_all_curated(connection: Connection) -> CuratedLoadResult:
    """Load MLB Statcast data into curated tables in dependency order.

    The caller owns the transaction. Exceptions from any loader are not
    caught here.
    """
    seasons = load_mlb_seasons(connection)
    games = load_games_from_statcast(connection)
    game_teams = load_game_teams_from_statcast(connection)
    game_players = load_game_players_from_statcast(connection)
    plate_appearances = load_plate_appearances_from_statcast(connection)
    pitches = load_pitches_from_statcast(connection)
    return CuratedLoadResult(
        seasons=seasons,
        games=games,
        game_teams=game_teams,
        game_players=game_players,
        plate_appearances=plate_appearances,
        pitches=pitches,
    )
