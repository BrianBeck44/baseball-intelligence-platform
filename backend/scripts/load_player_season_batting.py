"""One-time permanent load of analytics.player_season_batting."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.player_season_batting_data import (
    get_player_season_batting_games,
    transform_player_season_batting,
)
from app.analytics.player_season_batting_loader import load_player_season_batting
from app.core.config import settings


def main() -> int:
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        games = get_player_season_batting_games(connection)
        rows = transform_player_season_batting(connection, games)
        loaded_count = load_player_season_batting(connection, rows)
        row_count = int(
            connection.execute(
                text("SELECT COUNT(*) FROM analytics.player_season_batting")
            ).scalar_one()
        )
        transaction.commit()
        print("player_season_batting load succeeded.")
        print(f"extracted: {len(games)}")
        print(f"transformed: {len(rows)}")
        print(f"loaded: {loaded_count}")
        print(f"final row count: {row_count}")
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
