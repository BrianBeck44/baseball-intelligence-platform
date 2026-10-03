"""One-time permanent load of analytics.player_game_pitching."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.player_game_pitching_loader import (
    PlayerGamePitchingLoadResult,
    load_player_game_pitching_from_curated,
)
from app.core.config import settings

EXPECTED_EXTRACTED = 2500
EXPECTED_ROWS = 336
EXPECTED_TOTALS = {
    "batters_faced": 2500,
    "pitches": 9668,
    "hits_allowed": 489,
    "home_runs_allowed": 61,
    "walks": 222,
    "hit_by_pitch": 40,
    "strikeouts": 585,
}


def main() -> int:
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        result = load_player_game_pitching_from_curated(connection)
        totals = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS row_count,
                    COALESCE(SUM(batters_faced), 0)
                        AS batters_faced,
                    COALESCE(SUM(pitches), 0) AS pitches,
                    COALESCE(SUM(hits_allowed), 0)
                        AS hits_allowed,
                    COALESCE(SUM(home_runs_allowed), 0)
                        AS home_runs_allowed,
                    COALESCE(SUM(walks), 0) AS walks,
                    COALESCE(SUM(hit_by_pitch), 0)
                        AS hit_by_pitch,
                    COALESCE(SUM(strikeouts), 0) AS strikeouts
                FROM analytics.player_game_pitching
                """
            )
        ).mappings().one()
        invariants = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE home_runs_allowed > hits_allowed
                    ) AS home_runs_exceed_hits,
                    COUNT(*) FILTER (
                        WHERE hits_allowed > batters_faced
                    ) AS hits_exceed_batters_faced,
                    COUNT(*) FILTER (
                        WHERE walks > batters_faced
                    ) AS walks_exceed_batters_faced,
                    COUNT(*) FILTER (
                        WHERE hit_by_pitch > batters_faced
                    ) AS hbp_exceed_batters_faced,
                    COUNT(*) FILTER (
                        WHERE strikeouts > batters_faced
                    ) AS strikeouts_exceed_batters_faced,
                    COUNT(*) FILTER (
                        WHERE pitches < batters_faced
                    ) AS pitches_below_batters_faced
                FROM analytics.player_game_pitching
                """
            )
        ).mappings().one()
        duplicate_grains = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT pitcher_id, game_id, team_id
                    FROM analytics.player_game_pitching
                    GROUP BY pitcher_id, game_id, team_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
                """
            )
        ).scalar_one()
        _validate_load(
            result=result,
            totals=totals,
            invariants=invariants,
            duplicate_grains=int(duplicate_grains),
        )
        transaction.commit()
        print("Player Game Pitching load succeeded.")
        print(f"extracted: {result.extracted_count}")
        print(f"transformed: {result.transformed_count}")
        print(f"loaded: {result.loaded_count}")
        print(f"final row count: {int(totals['row_count'])}")
        print("aggregate validation: succeeded")
        print("commit: succeeded")
        return 0
    except Exception as exc:
        transaction.rollback()
        print(f"player_game_pitching load failed: {exc}")
        raise
    finally:
        connection.close()
        engine.dispose()


def _validate_load(
    *,
    result: PlayerGamePitchingLoadResult,
    totals,
    invariants,
    duplicate_grains: int,
) -> None:
    expected = {
        "extracted": EXPECTED_EXTRACTED,
        "transformed": EXPECTED_ROWS,
        "loaded": EXPECTED_ROWS,
        "rows": EXPECTED_ROWS,
        **EXPECTED_TOTALS,
        "duplicate_grains": 0,
        **{name: 0 for name in invariants.keys()},
    }
    actual = {
        "extracted": result.extracted_count,
        "transformed": result.transformed_count,
        "loaded": result.loaded_count,
        "rows": int(totals["row_count"]),
        **{name: int(totals[name]) for name in EXPECTED_TOTALS},
        "duplicate_grains": duplicate_grains,
        **{name: int(invariants[name]) for name in invariants.keys()},
    }
    mismatches = [
        f"{name}: expected {expected[name]}, got {actual[name]}"
        for name in expected
        if actual[name] != expected[name]
    ]
    if mismatches:
        raise ValueError(
            "player_game_pitching load validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
