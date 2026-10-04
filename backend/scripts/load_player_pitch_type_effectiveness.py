"""One-time permanent load of analytics.player_pitch_type_effectiveness."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.player_pitch_type_effectiveness_loader import (
    PlayerPitchTypeEffectivenessLoadResult,
    load_player_pitch_type_effectiveness_from_curated,
)
from app.core.config import settings

EXPECTED_EXTRACTED = 9645
EXPECTED_ROWS = 967
EXPECTED_TYPED_PITCHES = 9645


def main() -> int:
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        result = load_player_pitch_type_effectiveness_from_curated(connection)
        totals = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS row_count,
                    COALESCE(SUM(pitches), 0) AS pitches
                FROM analytics.player_pitch_type_effectiveness
                """
            )
        ).mappings().one()
        distinct_grains = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT player_id, pitch_type_id
                    FROM analytics.player_pitch_type_effectiveness
                    GROUP BY player_id, pitch_type_id
                ) AS grains
                """
            )
        ).scalar_one()
        duplicate_grains = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT player_id, pitch_type_id
                    FROM analytics.player_pitch_type_effectiveness
                    GROUP BY player_id, pitch_type_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
                """
            )
        ).scalar_one()
        source_typed_pitches = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM curated.pitch
                WHERE pitch_type_id IS NOT NULL
                """
            )
        ).scalar_one()
        invariants = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE whiffs > swings
                    ) AS whiffs_exceed_swings,
                    COUNT(*) FILTER (
                        WHERE swings > pitches
                    ) AS swings_exceed_pitches,
                    COUNT(*) FILTER (
                        WHERE balls_in_play > pitches
                    ) AS balls_in_play_exceed_pitches,
                    COUNT(*) FILTER (
                        WHERE called_strikes > pitches
                    ) AS called_strikes_exceed_pitches,
                    COUNT(*) FILTER (
                        WHERE fouls > swings
                    ) AS fouls_exceed_swings,
                    COUNT(*) FILTER (
                        WHERE hits_allowed > balls_in_play
                    ) AS hits_exceed_balls_in_play,
                    COUNT(*) FILTER (
                        WHERE home_runs_allowed > hits_allowed
                    ) AS home_runs_exceed_hits,
                    COUNT(*) FILTER (
                        WHERE strikeouts > plate_appearances
                    ) AS strikeouts_exceed_plate_appearances,
                    COUNT(*) FILTER (
                        WHERE walks > plate_appearances
                    ) AS walks_exceed_plate_appearances,
                    COUNT(*) FILTER (
                        WHERE hit_by_pitch > plate_appearances
                    ) AS hbp_exceed_plate_appearances
                FROM analytics.player_pitch_type_effectiveness
                """
            )
        ).mappings().one()
        rate_violations = connection.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE whiff_rate IS NOT NULL
                          AND (
                              whiff_rate < 0
                              OR whiff_rate > 1
                          )
                    ) AS whiff_rate_out_of_range,
                    COUNT(*) FILTER (
                        WHERE called_strike_rate IS NOT NULL
                          AND (
                              called_strike_rate < 0
                              OR called_strike_rate > 1
                          )
                    ) AS called_strike_rate_out_of_range,
                    COUNT(*) FILTER (
                        WHERE swing_rate IS NOT NULL
                          AND (
                              swing_rate < 0
                              OR swing_rate > 1
                          )
                    ) AS swing_rate_out_of_range,
                    COUNT(*) FILTER (
                        WHERE contact_rate IS NOT NULL
                          AND (
                              contact_rate < 0
                              OR contact_rate > 1
                          )
                    ) AS contact_rate_out_of_range,
                    COUNT(*) FILTER (
                        WHERE strikeout_rate IS NOT NULL
                          AND (
                              strikeout_rate < 0
                              OR strikeout_rate > 1
                          )
                    ) AS strikeout_rate_out_of_range
                FROM analytics.player_pitch_type_effectiveness
                """
            )
        ).mappings().one()
        _validate_load(
            result=result,
            totals=totals,
            distinct_grains=int(distinct_grains),
            duplicate_grains=int(duplicate_grains),
            source_typed_pitches=int(source_typed_pitches),
            invariants=invariants,
            rate_violations=rate_violations,
        )
        print("aggregate validation: succeeded")
        transaction.commit()
        print("Pitch type effectiveness load complete.")
        print(f"Extracted: {result.extracted_count}")
        print(f"Transformed: {result.transformed_count}")
        print(f"Loaded: {result.loaded_count}")
        print(f"Final rows: {int(totals['row_count'])}")
        print("commit: succeeded")
        return 0
    except Exception as exc:
        transaction.rollback()
        print(f"player_pitch_type_effectiveness load failed: {exc}")
        raise
    finally:
        connection.close()
        engine.dispose()


def _validate_load(
    *,
    result: PlayerPitchTypeEffectivenessLoadResult,
    totals,
    distinct_grains: int,
    duplicate_grains: int,
    source_typed_pitches: int,
    invariants,
    rate_violations,
) -> None:
    expected = {
        "extracted": EXPECTED_EXTRACTED,
        "transformed": EXPECTED_ROWS,
        "loaded": EXPECTED_ROWS,
        "rows": EXPECTED_ROWS,
        "pitches": EXPECTED_TYPED_PITCHES,
        "source_typed_pitches": EXPECTED_TYPED_PITCHES,
        "distinct_grains": EXPECTED_ROWS,
        "duplicate_grains": 0,
        **{name: 0 for name in invariants.keys()},
        **{name: 0 for name in rate_violations.keys()},
    }
    actual = {
        "extracted": result.extracted_count,
        "transformed": result.transformed_count,
        "loaded": result.loaded_count,
        "rows": int(totals["row_count"]),
        "pitches": int(totals["pitches"]),
        "source_typed_pitches": source_typed_pitches,
        "distinct_grains": distinct_grains,
        "duplicate_grains": duplicate_grains,
        **{name: int(invariants[name]) for name in invariants.keys()},
        **{
            name: int(rate_violations[name])
            for name in rate_violations.keys()
        },
    }
    mismatches = [
        f"{name}: expected {expected[name]}, got {actual[name]}"
        for name in expected
        if actual[name] != expected[name]
    ]
    if mismatches:
        raise ValueError(
            "player_pitch_type_effectiveness load validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
