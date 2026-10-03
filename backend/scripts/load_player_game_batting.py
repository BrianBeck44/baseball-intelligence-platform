"""One-time permanent load of analytics.player_game_batting."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.player_game_batting_loader import (
    PlayerGameBattingLoadResult,
    load_player_game_batting_from_curated,
)
from app.core.config import settings

EXPECTED_EXTRACTED = 2500
EXPECTED_ROWS = 672
EXPECTED_TOTALS = {
    "plate_appearances": 2500,
    "at_bats": 2203,
    "hits": 489,
    "singles": 325,
    "doubles": 98,
    "triples": 5,
    "home_runs": 61,
    "walks": 222,
    "hit_by_pitch": 40,
    "strikeouts": 585,
    "sacrifice_flies": 19,
    "sacrifice_bunts": 8,
}


def main() -> int:
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        result = load_player_game_batting_from_curated(connection)
        totals = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS row_count,
                    COALESCE(SUM(plate_appearances), 0)
                        AS plate_appearances,
                    COALESCE(SUM(at_bats), 0) AS at_bats,
                    COALESCE(SUM(hits), 0) AS hits,
                    COALESCE(SUM(singles), 0) AS singles,
                    COALESCE(SUM(doubles), 0) AS doubles,
                    COALESCE(SUM(triples), 0) AS triples,
                    COALESCE(SUM(home_runs), 0) AS home_runs,
                    COALESCE(SUM(walks), 0) AS walks,
                    COALESCE(SUM(hit_by_pitch), 0) AS hit_by_pitch,
                    COALESCE(SUM(strikeouts), 0) AS strikeouts,
                    COALESCE(SUM(sacrifice_flies), 0)
                        AS sacrifice_flies,
                    COALESCE(SUM(sacrifice_bunts), 0)
                        AS sacrifice_bunts
                FROM analytics.player_game_batting
                """
            )
        ).mappings().one()
        _validate_load(result=result, totals=totals)
        transaction.commit()
        print("player_game_batting load succeeded.")
        print(f"extracted: {result.extracted_count}")
        print(f"transformed: {result.transformed_count}")
        print(f"loaded: {result.loaded_count}")
        print(f"final row count: {int(totals['row_count'])}")
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


def _validate_load(
    *,
    result: PlayerGameBattingLoadResult,
    totals,
) -> None:
    expected = {
        "extracted": EXPECTED_EXTRACTED,
        "transformed": EXPECTED_ROWS,
        "loaded": EXPECTED_ROWS,
        "rows": EXPECTED_ROWS,
        **EXPECTED_TOTALS,
    }
    actual = {
        "extracted": result.extracted_count,
        "transformed": result.transformed_count,
        "loaded": result.loaded_count,
        "rows": int(totals["row_count"]),
        **{name: int(totals[name]) for name in EXPECTED_TOTALS},
    }
    mismatches = [
        f"{name}: expected {expected[name]}, got {actual[name]}"
        for name in expected
        if actual[name] != expected[name]
    ]
    if mismatches:
        raise ValueError(
            "player_game_batting load validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
