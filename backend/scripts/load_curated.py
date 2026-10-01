"""CLI adapter for loading curated baseball entities from Statcast."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine

from app.core.config import settings
from app.curated.load_all import load_all_curated


def main() -> int:
    engine = create_engine(settings.database_url)

    try:
        with engine.begin() as connection:
            result = load_all_curated(connection)
    finally:
        engine.dispose()

    print("Curated load complete.")
    print(
        "Seasons loaded: "
        f"{result.seasons.seasons_loaded}"
    )
    print(f"Teams: {result.teams}")
    print(
        "Players found/resolved/loaded: "
        f"{result.players.player_ids_found}/"
        f"{result.players.players_resolved}/"
        f"{result.players.players_loaded}"
    )
    print(
        "Games supplied/loaded: "
        f"{result.games.games_supplied}/{result.games.games_loaded}"
    )
    print(
        "Game teams supplied/loaded: "
        f"{result.game_teams.game_teams_supplied}/"
        f"{result.game_teams.game_teams_loaded}"
    )
    print(
        "Game players supplied/loaded: "
        f"{result.game_players.game_players_supplied}/"
        f"{result.game_players.game_players_loaded}"
    )
    print(
        "Plate appearances found/loaded: "
        f"{result.plate_appearances.plate_appearances_found}/"
        f"{result.plate_appearances.plate_appearances_loaded}"
    )
    print(
        "Pitches found/loaded: "
        f"{result.pitches.pitches_found}/{result.pitches.pitches_loaded}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
