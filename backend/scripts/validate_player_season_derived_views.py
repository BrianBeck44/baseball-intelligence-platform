"""Validate the player-season derived analytics views.

Read-only checks compare the views to their source season tables.
The transaction is always rolled back.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.core.config import settings

_RATE_TOLERANCE = "0.000001"


def main() -> int:
    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                counts = _collect_validations(connection)
                _print_report(counts)
                _validate_views(counts)
                print("Player Season derived views validation succeeded.")
            finally:
                transaction.rollback()
                print("rollback: succeeded")
    finally:
        engine.dispose()

    return 0


def _collect_validations(connection: Connection) -> dict[str, int]:
    season_batting_rows = int(
        connection.execute(
            text("SELECT COUNT(*) FROM analytics.player_season_batting")
        ).scalar_one()
    )
    batting_view_rows = int(
        connection.execute(
            text(
                "SELECT COUNT(*) FROM analytics.v_player_season_batting_derived"
            )
        ).scalar_one()
    )
    batting_row_count_mismatches = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_season_batting AS season
                FULL OUTER JOIN analytics.v_player_season_batting_derived
                    AS derived
                  ON derived.player_id = season.player_id
                 AND derived.season_id = season.season_id
                WHERE season.player_id IS NULL
                   OR derived.player_id IS NULL
                """
            )
        ).scalar_one()
    )
    batting_duplicate_grains = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT player_id, season_id
                    FROM analytics.v_player_season_batting_derived
                    GROUP BY player_id, season_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
                """
            )
        ).scalar_one()
    )
    batting_null_identity = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.v_player_season_batting_derived
                WHERE player_id IS NULL
                   OR season_id IS NULL
                """
            )
        ).scalar_one()
    )
    extra_base_hit_mismatches = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.v_player_season_batting_derived
                WHERE extra_base_hits IS DISTINCT FROM
                    (doubles + triples + home_runs)
                """
            )
        ).scalar_one()
    )
    total_base_mismatches = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.v_player_season_batting_derived
                WHERE total_bases IS DISTINCT FROM
                    (
                        singles
                        + (2 * doubles)
                        + (3 * triples)
                        + (4 * home_runs)
                    )
                """
            )
        ).scalar_one()
    )
    isolated_power_mismatches = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.v_player_season_batting_derived
                WHERE (
                    at_bats = 0
                    AND isolated_power IS NOT NULL
                )
                OR (
                    at_bats > 0
                    AND (
                        isolated_power IS NULL
                        OR ABS(
                            isolated_power
                            - (
                                (total_bases - hits)::numeric
                                / at_bats
                            )
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    season_pitching_rows = int(
        connection.execute(
            text("SELECT COUNT(*) FROM analytics.player_season_pitching")
        ).scalar_one()
    )
    pitching_view_rows = int(
        connection.execute(
            text(
                "SELECT COUNT(*) FROM analytics.v_player_season_pitching_rates"
            )
        ).scalar_one()
    )
    pitching_row_count_mismatches = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_season_pitching AS season
                FULL OUTER JOIN analytics.v_player_season_pitching_rates
                    AS derived
                  ON derived.player_id = season.player_id
                 AND derived.season_id = season.season_id
                WHERE season.player_id IS NULL
                   OR derived.player_id IS NULL
                """
            )
        ).scalar_one()
    )
    pitching_duplicate_grains = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT player_id, season_id
                    FROM analytics.v_player_season_pitching_rates
                    GROUP BY player_id, season_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
                """
            )
        ).scalar_one()
    )
    pitching_null_identity = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.v_player_season_pitching_rates
                WHERE player_id IS NULL
                   OR season_id IS NULL
                """
            )
        ).scalar_one()
    )
    strikeout_rate_mismatches = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.v_player_season_pitching_rates
                WHERE (
                    batters_faced = 0
                    AND strikeout_rate IS NOT NULL
                )
                OR (
                    batters_faced > 0
                    AND (
                        strikeout_rate IS NULL
                        OR ABS(
                            strikeout_rate
                            - (strikeouts::numeric / batters_faced)
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    walk_rate_mismatches = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.v_player_season_pitching_rates
                WHERE (
                    batters_faced = 0
                    AND walk_rate IS NOT NULL
                )
                OR (
                    batters_faced > 0
                    AND (
                        walk_rate IS NULL
                        OR ABS(
                            walk_rate
                            - (walks::numeric / batters_faced)
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    strikeout_to_walk_mismatches = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.v_player_season_pitching_rates
                WHERE (
                    walks = 0
                    AND strikeout_to_walk_ratio IS NOT NULL
                )
                OR (
                    walks > 0
                    AND (
                        strikeout_to_walk_ratio IS NULL
                        OR ABS(
                            strikeout_to_walk_ratio
                            - (strikeouts::numeric / walks)
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    return {
        "season_batting_rows": season_batting_rows,
        "batting_view_rows": batting_view_rows,
        "batting_row_count_mismatches": batting_row_count_mismatches,
        "batting_duplicate_grains": batting_duplicate_grains,
        "batting_null_identity": batting_null_identity,
        "extra_base_hit_mismatches": extra_base_hit_mismatches,
        "total_base_mismatches": total_base_mismatches,
        "isolated_power_mismatches": isolated_power_mismatches,
        "season_pitching_rows": season_pitching_rows,
        "pitching_view_rows": pitching_view_rows,
        "pitching_row_count_mismatches": pitching_row_count_mismatches,
        "pitching_duplicate_grains": pitching_duplicate_grains,
        "pitching_null_identity": pitching_null_identity,
        "strikeout_rate_mismatches": strikeout_rate_mismatches,
        "walk_rate_mismatches": walk_rate_mismatches,
        "strikeout_to_walk_mismatches": strikeout_to_walk_mismatches,
    }


def _print_report(counts: dict[str, int]) -> None:
    print("Player Season derived views validation")
    print()
    print(f"season_batting_rows: {counts['season_batting_rows']}")
    print(f"batting_view_rows: {counts['batting_view_rows']}")
    print(
        "batting_row_count_mismatches: "
        f"{counts['batting_row_count_mismatches']}"
    )
    print(f"batting_duplicate_grains: {counts['batting_duplicate_grains']}")
    print(f"batting_null_identity: {counts['batting_null_identity']}")
    print(f"extra_base_hit_mismatches: {counts['extra_base_hit_mismatches']}")
    print(f"total_base_mismatches: {counts['total_base_mismatches']}")
    print(f"isolated_power_mismatches: {counts['isolated_power_mismatches']}")
    print(f"season_pitching_rows: {counts['season_pitching_rows']}")
    print(f"pitching_view_rows: {counts['pitching_view_rows']}")
    print(
        "pitching_row_count_mismatches: "
        f"{counts['pitching_row_count_mismatches']}"
    )
    print(f"pitching_duplicate_grains: {counts['pitching_duplicate_grains']}")
    print(f"pitching_null_identity: {counts['pitching_null_identity']}")
    print(f"strikeout_rate_mismatches: {counts['strikeout_rate_mismatches']}")
    print(f"walk_rate_mismatches: {counts['walk_rate_mismatches']}")
    print(
        "strikeout_to_walk_mismatches: "
        f"{counts['strikeout_to_walk_mismatches']}"
    )


def _validate_views(counts: dict[str, int]) -> None:
    expected_zero = (
        "batting_row_count_mismatches",
        "batting_duplicate_grains",
        "batting_null_identity",
        "extra_base_hit_mismatches",
        "total_base_mismatches",
        "isolated_power_mismatches",
        "pitching_row_count_mismatches",
        "pitching_duplicate_grains",
        "pitching_null_identity",
        "strikeout_rate_mismatches",
        "walk_rate_mismatches",
        "strikeout_to_walk_mismatches",
    )
    expected = {
        **{name: 0 for name in expected_zero},
        "batting_view_rows": counts["season_batting_rows"],
        "pitching_view_rows": counts["season_pitching_rows"],
    }
    mismatches = [
        f"{name}: expected {expected[name]}, got {counts[name]}"
        for name in expected
        if counts[name] != expected[name]
    ]
    if mismatches:
        raise ValueError(
            "player_season derived views validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
