"""One-off validation of the player-game batting analytics pipeline.

Extracts, transforms, and loads into a transaction that is always rolled
back so analytics.player_game_batting is not permanently populated.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.analytics.player_game_batting_data import (
    get_player_game_batting_appearances,
    load_player_game_batting,
    transform_player_game_batting,
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

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                appearances = get_player_game_batting_appearances(connection)
                print(f"Extracted plate appearances: {len(appearances)}")

                rows = transform_player_game_batting(connection, appearances)
                print(f"Transformed player/game/team rows: {len(rows)}")

                loaded = load_player_game_batting(connection, rows)
                print(f"Loaded rows: {loaded}")

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

                print("Analytics totals:")
                print(f"  rows: {totals['row_count']}")
                for name in EXPECTED_TOTALS:
                    print(f"  {name}: {totals[name]}")

                _validate_pipeline(
                    extracted=len(appearances),
                    transformed=len(rows),
                    loaded=loaded,
                    totals=totals,
                )
                print("player_game_batting pipeline validation succeeded.")
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

    return 0


def _validate_pipeline(
    *,
    extracted: int,
    transformed: int,
    loaded: int,
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
        "extracted": extracted,
        "transformed": transformed,
        "loaded": loaded,
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
            "player_game_batting pipeline validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
