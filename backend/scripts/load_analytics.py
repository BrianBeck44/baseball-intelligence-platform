"""Rebuild analytics tables from the current curated dataset."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine

from app.analytics.load_all import load_all_analytics
from app.analytics.rebuild_validation import validate_analytics_rebuild
from app.core.config import settings


def main() -> int:
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        result = load_all_analytics(connection)
        validate_analytics_rebuild(connection, result)
        transaction.commit()
        print("Analytics rebuild succeeded.")
        print(
            "Game batting extracted/transformed/loaded: "
            f"{result.game_batting.extracted_count}/"
            f"{result.game_batting.transformed_count}/"
            f"{result.game_batting.loaded_count}"
        )
        print(
            "Game pitching extracted/transformed/loaded: "
            f"{result.game_pitching.extracted_count}/"
            f"{result.game_pitching.transformed_count}/"
            f"{result.game_pitching.loaded_count}"
        )
        print(
            "Pitch-type effectiveness extracted/transformed/loaded: "
            f"{result.pitch_type_effectiveness.extracted_count}/"
            f"{result.pitch_type_effectiveness.transformed_count}/"
            f"{result.pitch_type_effectiveness.loaded_count}"
        )
        print(
            "Season batting extracted/transformed/loaded: "
            f"{result.season_batting.extracted_count}/"
            f"{result.season_batting.transformed_count}/"
            f"{result.season_batting.loaded_count}"
        )
        print(
            "Season pitching extracted/transformed/loaded: "
            f"{result.season_pitching.extracted_count}/"
            f"{result.season_pitching.transformed_count}/"
            f"{result.season_pitching.loaded_count}"
        )
        print("aggregate validation: succeeded")
        print("commit: succeeded")
        return 0
    except Exception as exc:
        transaction.rollback()
        print(f"Analytics rebuild failed: {exc}")
        raise
    finally:
        connection.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
