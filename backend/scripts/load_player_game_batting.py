"""Replace analytics.player_game_batting from curated plate appearances."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.player_game_batting_loader import (
    load_player_game_batting_from_curated,
)
from app.analytics.rebuild_validation import validate_player_game_batting_load
from app.core.config import settings


def main() -> int:
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(text("DELETE FROM analytics.player_game_batting"))
        result = load_player_game_batting_from_curated(connection)
        validate_player_game_batting_load(connection, result)
        transaction.commit()
        print("player_game_batting load succeeded.")
        print(f"extracted: {result.extracted_count}")
        print(f"transformed: {result.transformed_count}")
        print(f"loaded: {result.loaded_count}")
        print("aggregate validation: succeeded")
        print("commit: succeeded")
        return 0
    except Exception as exc:
        transaction.rollback()
        print(f"player_game_batting load failed: {exc}")
        raise
    finally:
        connection.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
