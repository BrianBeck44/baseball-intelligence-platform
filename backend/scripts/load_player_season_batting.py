"""Replace analytics.player_season_batting from game-level batting."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.load_all import SeasonLoadResult
from app.analytics.player_season_batting_data import (
    get_player_season_batting_games,
    transform_player_season_batting,
)
from app.analytics.player_season_batting_loader import load_player_season_batting
from app.analytics.rebuild_validation import validate_player_season_batting_load
from app.core.config import settings


def main() -> int:
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(text("DELETE FROM analytics.player_season_batting"))
        games = get_player_season_batting_games(connection)
        rows = transform_player_season_batting(connection, games)
        loaded_count = load_player_season_batting(connection, rows)
        result = SeasonLoadResult(
            extracted_count=len(games),
            transformed_count=len(rows),
            loaded_count=loaded_count,
        )
        validate_player_season_batting_load(connection, result)
        transaction.commit()
        print("player_season_batting load succeeded.")
        print(f"extracted: {result.extracted_count}")
        print(f"transformed: {result.transformed_count}")
        print(f"loaded: {result.loaded_count}")
        print("aggregate validation: succeeded")
        print("commit: succeeded")
        return 0
    except Exception as exc:
        transaction.rollback()
        print(f"player_season_batting load failed: {exc}")
        raise
    finally:
        connection.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
