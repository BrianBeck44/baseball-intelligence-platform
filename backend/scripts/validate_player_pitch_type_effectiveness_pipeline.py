"""One-off validation of the pitch-type effectiveness analytics pipeline.

Extracts, transforms, and loads into a transaction that is always rolled
back so analytics.player_pitch_type_effectiveness is not permanently
populated.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.player_pitch_type_effectiveness_loader import (
    PlayerPitchTypeEffectivenessLoadResult,
    load_player_pitch_type_effectiveness_from_curated,
)
from app.core.config import settings


def main() -> int:
    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                pre_load_count = int(
                    connection.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM analytics.player_pitch_type_effectiveness
                            """
                        )
                    ).scalar_one()
                )

                result = load_player_pitch_type_effectiveness_from_curated(
                    connection
                )
                print(f"extracted: {result.extracted_count}")
                print(f"transformed: {result.transformed_count}")
                print(f"loaded: {result.loaded_count}")

                totals = connection.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) AS row_count,
                            COALESCE(SUM(pitches), 0) AS pitches,
                            COALESCE(SUM(plate_appearances), 0)
                                AS plate_appearances,
                            COALESCE(SUM(hits_allowed), 0)
                                AS hits_allowed,
                            COALESCE(SUM(home_runs_allowed), 0)
                                AS home_runs_allowed,
                            COALESCE(SUM(strikeouts), 0) AS strikeouts,
                            COALESCE(SUM(walks), 0) AS walks,
                            COALESCE(SUM(hit_by_pitch), 0)
                                AS hit_by_pitch
                        FROM analytics.player_pitch_type_effectiveness
                        """
                    )
                ).mappings().one()

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
                source_grain = connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM (
                            SELECT
                                pa.pitcher_id,
                                pitch.pitch_type_id
                            FROM curated.pitch
                            JOIN curated.plate_appearance AS pa
                              ON pa.plate_appearance_id
                                 = pitch.plate_appearance_id
                            WHERE pitch.pitch_type_id IS NOT NULL
                            GROUP BY
                                pa.pitcher_id,
                                pitch.pitch_type_id
                        ) AS grains
                        """
                    )
                ).scalar_one()

                print(f"final row count: {int(totals['row_count'])}")
                print("aggregate totals:")
                for name in (
                    "pitches",
                    "plate_appearances",
                    "hits_allowed",
                    "home_runs_allowed",
                    "strikeouts",
                    "walks",
                    "hit_by_pitch",
                ):
                    print(f"  {name}: {totals[name]}")
                print(f"source typed pitches: {int(source_typed_pitches)}")
                print(f"source grain: {int(source_grain)}")
                print(f"duplicate grains: {int(duplicate_grains)}")
                print("metric integrity violations:")
                for name in invariants.keys():
                    print(f"  {name}: {invariants[name]}")
                print("rate integrity violations:")
                for name in rate_violations.keys():
                    print(f"  {name}: {rate_violations[name]}")

                _validate_pipeline(
                    result=result,
                    totals=totals,
                    invariants=invariants,
                    rate_violations=rate_violations,
                    duplicate_grains=int(duplicate_grains),
                    source_typed_pitches=int(source_typed_pitches),
                    source_grain=int(source_grain),
                )
                print(
                    "player_pitch_type_effectiveness pipeline "
                    "validation succeeded."
                )
            except Exception:
                transaction.rollback()
                raise
            else:
                transaction.rollback()
                persisted_count = int(
                    connection.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM analytics.player_pitch_type_effectiveness
                            """
                        )
                    ).scalar_one()
                )
                print("rollback: succeeded")
                print(f"pre-load row count: {pre_load_count}")
                print(f"persisted row count: {persisted_count}")
                if persisted_count != pre_load_count:
                    raise ValueError(
                        "player_pitch_type_effectiveness rollback "
                        "verification failed: "
                        f"expected persisted row count {pre_load_count}, "
                        f"got {persisted_count}"
                    )
                print("rollback verification: succeeded")
    finally:
        engine.dispose()

    return 0


def _validate_pipeline(
    *,
    result: PlayerPitchTypeEffectivenessLoadResult,
    totals,
    invariants,
    rate_violations,
    duplicate_grains: int,
    source_typed_pitches: int,
    source_grain: int,
) -> None:
    expected = {
        "extracted": source_typed_pitches,
        "transformed": source_grain,
        "loaded": source_grain,
        "rows": source_grain,
        "pitches": source_typed_pitches,
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
            "player_pitch_type_effectiveness pipeline validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
