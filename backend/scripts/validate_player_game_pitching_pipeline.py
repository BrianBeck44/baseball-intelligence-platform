"""One-off validation of the player-game pitching analytics pipeline.

Extracts, transforms, and loads into a transaction that is always rolled
back so analytics.player_game_pitching is not permanently populated.
"""

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
EXPECTED_SOURCE = {
    "plate_appearances": 2500,
    "hits": 489,
    "home_runs": 61,
    "walks": 222,
    "hit_by_pitch": 40,
    "strikeouts": 585,
    "pitches": 9668,
}


def main() -> int:
    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                result = load_player_game_pitching_from_curated(connection)
                print(f"extracted: {result.extracted_count}")
                print(f"transformed: {result.transformed_count}")
                print(f"loaded: {result.loaded_count}")

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
                                WHERE pitcher_id IS NULL
                            ) AS null_pitcher_id,
                            COUNT(*) FILTER (
                                WHERE game_id IS NULL
                            ) AS null_game_id,
                            COUNT(*) FILTER (
                                WHERE team_id IS NULL
                            ) AS null_team_id,
                            COUNT(*) FILTER (
                                WHERE batters_faced < 0
                            ) AS negative_batters_faced,
                            COUNT(*) FILTER (
                                WHERE pitches < 0
                            ) AS negative_pitches,
                            COUNT(*) FILTER (
                                WHERE hits_allowed < 0
                            ) AS negative_hits_allowed,
                            COUNT(*) FILTER (
                                WHERE home_runs_allowed < 0
                            ) AS negative_home_runs_allowed,
                            COUNT(*) FILTER (
                                WHERE walks < 0
                            ) AS negative_walks,
                            COUNT(*) FILTER (
                                WHERE hit_by_pitch < 0
                            ) AS negative_hit_by_pitch,
                            COUNT(*) FILTER (
                                WHERE strikeouts < 0
                            ) AS negative_strikeouts,
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

                source = connection.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) AS plate_appearances,
                            COUNT(*) FILTER (
                                WHERE ot.code IN (
                                    'single',
                                    'double',
                                    'triple',
                                    'home_run'
                                )
                            ) AS hits,
                            COUNT(*) FILTER (
                                WHERE ot.code = 'home_run'
                            ) AS home_runs,
                            COUNT(*) FILTER (
                                WHERE ot.code IN (
                                    'walk',
                                    'intent_walk'
                                )
                            ) AS walks,
                            COUNT(*) FILTER (
                                WHERE ot.code = 'hit_by_pitch'
                            ) AS hit_by_pitch,
                            COUNT(*) FILTER (
                                WHERE ot.code IN (
                                    'strikeout',
                                    'strikeout_double_play'
                                )
                            ) AS strikeouts
                        FROM curated.plate_appearance AS pa
                        LEFT JOIN curated.outcome_type AS ot
                          ON ot.id = pa.outcome_type_id
                        """
                    )
                ).mappings().one()
                source_pitches = connection.execute(
                    text("SELECT COUNT(*) FROM curated.pitch")
                ).scalar_one()

                print(f"final row count: {int(totals['row_count'])}")
                print("aggregate totals:")
                for name in EXPECTED_TOTALS:
                    print(f"  {name}: {totals[name]}")

                _validate_pipeline(
                    result=result,
                    totals=totals,
                    invariants=invariants,
                    duplicate_grains=int(duplicate_grains),
                    source=source,
                    source_pitches=int(source_pitches),
                )
                print("player_game_pitching pipeline validation succeeded.")
            except Exception:
                transaction.rollback()
                raise
            else:
                transaction.rollback()
                print("rollback: succeeded")
    finally:
        engine.dispose()

    return 0


def _validate_pipeline(
    *,
    result: PlayerGamePitchingLoadResult,
    totals,
    invariants,
    duplicate_grains: int,
    source,
    source_pitches: int,
) -> None:
    expected = {
        "extracted": EXPECTED_EXTRACTED,
        "transformed": EXPECTED_ROWS,
        "loaded": EXPECTED_ROWS,
        "rows": EXPECTED_ROWS,
        **EXPECTED_TOTALS,
        **{f"source_{name}": value for name, value in EXPECTED_SOURCE.items()},
        "analytics_pitches_match_curated_pitch": EXPECTED_SOURCE["pitches"],
        "duplicate_grains": 0,
        **{name: 0 for name in invariants.keys()},
    }
    actual = {
        "extracted": result.extracted_count,
        "transformed": result.transformed_count,
        "loaded": result.loaded_count,
        "rows": int(totals["row_count"]),
        **{name: int(totals[name]) for name in EXPECTED_TOTALS},
        **{f"source_{name}": int(source[name]) for name in source.keys()},
        "source_pitches": source_pitches,
        "analytics_pitches_match_curated_pitch": int(totals["pitches"]),
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
            "player_game_pitching pipeline validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
