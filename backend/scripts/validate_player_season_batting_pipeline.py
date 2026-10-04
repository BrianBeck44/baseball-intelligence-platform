"""Validate the player-season batting analytics pipeline.

Read-only checks run against the currently persisted season batting
rows. A temporary extract/transform/load is then executed in a
transaction that is always rolled back so production rows are not
changed.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.analytics.player_season_batting_data import (
    get_player_season_batting_games,
    transform_player_season_batting,
)
from app.analytics.player_season_batting_loader import load_player_season_batting
from app.core.config import settings

_COUNT_METRICS = (
    "games",
    "plate_appearances",
    "at_bats",
    "hits",
    "singles",
    "doubles",
    "triples",
    "home_runs",
    "walks",
    "hit_by_pitch",
    "strikeouts",
    "sacrifice_flies",
    "sacrifice_bunts",
)
_SUM_METRICS = tuple(name for name in _COUNT_METRICS if name != "games")
_RATE_TOLERANCE = "0.000001"


def main() -> int:
    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                pre_reload = _snapshot(connection)
                if int(pre_reload["row_count"]) <= 0:
                    raise ValueError(
                        "player_season_batting pipeline validation failed:\n"
                        "  season_batting_rows: expected > 0, got 0"
                    )

                counts = _collect_validations(connection)
                counts["pre_reload_row_count"] = int(pre_reload["row_count"])

                games = get_player_season_batting_games(connection)
                rows = transform_player_season_batting(connection, games)
                loaded_count = load_player_season_batting(connection, rows)
                reload_snapshot = _snapshot(connection)

                counts["reload_transformed_count"] = len(rows)
                counts["reload_loaded_count"] = loaded_count
                counts["reload_row_count"] = int(reload_snapshot["row_count"])
                counts["reload_snapshot_violations"] = int(
                    reload_snapshot != pre_reload
                )

                _print_report(counts)
                _validate_pipeline(counts, pre_reload=pre_reload)
                print("Player Season Batting pipeline validation succeeded.")
            except Exception:
                transaction.rollback()
                raise
            else:
                transaction.rollback()
                post_reload = _snapshot(connection)
                rollback_violations = int(post_reload != pre_reload)
                print(f"post_rollback_row_count: {int(post_reload['row_count'])}")
                print(f"rollback_violations: {rollback_violations}")
                print("rollback: succeeded")
                if rollback_violations:
                    raise ValueError(
                        "player_season_batting pipeline validation failed:\n"
                        "  rollback_violations: expected 0, "
                        f"got {rollback_violations}"
                    )
                print("rollback verification: succeeded")
    finally:
        engine.dispose()

    return 0


def _snapshot(connection: Connection):
    return dict(
        connection.execute(
            text(
                """
                SELECT
                    COUNT(*) AS row_count,
                    COALESCE(SUM(games), 0) AS games,
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
                FROM analytics.player_season_batting
                """
            )
        ).mappings().one()
    )


def _collect_validations(connection: Connection) -> dict[str, int]:
    game_batting_rows = int(
        connection.execute(
            text("SELECT COUNT(*) FROM analytics.player_game_batting")
        ).scalar_one()
    )
    season_batting_rows = int(
        connection.execute(
            text("SELECT COUNT(*) FROM analytics.player_season_batting")
        ).scalar_one()
    )
    duplicate_grains = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT player_id, season_id
                    FROM analytics.player_season_batting
                    GROUP BY player_id, season_id
                    HAVING COUNT(*) > 1
                ) AS duplicates
                """
            )
        ).scalar_one()
    )
    orphan_players = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_season_batting AS season
                LEFT JOIN curated.player AS player
                  ON player.player_id = season.player_id
                WHERE player.player_id IS NULL
                """
            )
        ).scalar_one()
    )
    orphan_seasons = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_season_batting AS season
                LEFT JOIN curated.season AS season_ref
                  ON season_ref.season_id = season.season_id
                WHERE season_ref.season_id IS NULL
                """
            )
        ).scalar_one()
    )
    game_count_mismatches = int(
        connection.execute(
            text(
                """
                WITH source AS (
                    SELECT
                        batting.player_id,
                        game.season_id,
                        COUNT(DISTINCT batting.game_id) AS games
                    FROM analytics.player_game_batting AS batting
                    JOIN curated.game AS game
                      ON game.game_id = batting.game_id
                    GROUP BY batting.player_id, game.season_id
                )
                SELECT COUNT(*)
                FROM analytics.player_season_batting AS season
                FULL OUTER JOIN source
                  ON source.player_id = season.player_id
                 AND source.season_id = season.season_id
                WHERE season.games IS DISTINCT FROM source.games
                """
            )
        ).scalar_one()
    )
    count_metric_mismatches = int(
        connection.execute(
            text(
                f"""
                WITH source AS (
                    SELECT
                        batting.player_id,
                        game.season_id,
                        {", ".join(
                            f"SUM(batting.{name}) AS {name}"
                            for name in _SUM_METRICS
                        )}
                    FROM analytics.player_game_batting AS batting
                    JOIN curated.game AS game
                      ON game.game_id = batting.game_id
                    GROUP BY batting.player_id, game.season_id
                )
                SELECT COUNT(*)
                FROM analytics.player_season_batting AS season
                FULL OUTER JOIN source
                  ON source.player_id = season.player_id
                 AND source.season_id = season.season_id
                WHERE {" OR ".join(
                    f"season.{name} IS DISTINCT FROM source.{name}"
                    for name in _SUM_METRICS
                )}
                """
            )
        ).scalar_one()
    )
    hit_component_violations = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE hits IS DISTINCT FROM
                    (singles + doubles + triples + home_runs)
                """
            )
        ).scalar_one()
    )
    batting_average_violations = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE (
                    at_bats = 0
                    AND batting_average IS NOT NULL
                )
                OR (
                    at_bats > 0
                    AND (
                        batting_average IS NULL
                        OR ABS(
                            batting_average
                            - (hits::numeric / at_bats)
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    on_base_percentage_violations = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE (
                    (at_bats + walks + hit_by_pitch + sacrifice_flies) = 0
                    AND on_base_percentage IS NOT NULL
                )
                OR (
                    (at_bats + walks + hit_by_pitch + sacrifice_flies) > 0
                    AND (
                        on_base_percentage IS NULL
                        OR ABS(
                            on_base_percentage
                            - (
                                (hits + walks + hit_by_pitch)::numeric
                                / (
                                    at_bats
                                    + walks
                                    + hit_by_pitch
                                    + sacrifice_flies
                                )
                            )
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    slugging_percentage_violations = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE (
                    at_bats = 0
                    AND slugging_percentage IS NOT NULL
                )
                OR (
                    at_bats > 0
                    AND (
                        slugging_percentage IS NULL
                        OR ABS(
                            slugging_percentage
                            - (
                                (
                                    singles
                                    + (2 * doubles)
                                    + (3 * triples)
                                    + (4 * home_runs)
                                )::numeric
                                / at_bats
                            )
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    ops_violations = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE (
                    (
                        on_base_percentage IS NULL
                        OR slugging_percentage IS NULL
                    )
                    AND ops IS NOT NULL
                )
                OR (
                    on_base_percentage IS NOT NULL
                    AND slugging_percentage IS NOT NULL
                    AND (
                        ops IS NULL
                        OR ABS(
                            ops
                            - (on_base_percentage + slugging_percentage)
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    strikeout_rate_violations = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE (
                    plate_appearances = 0
                    AND strikeout_rate IS NOT NULL
                )
                OR (
                    plate_appearances > 0
                    AND (
                        strikeout_rate IS NULL
                        OR ABS(
                            strikeout_rate
                            - (strikeouts::numeric / plate_appearances)
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    walk_rate_violations = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE (
                    plate_appearances = 0
                    AND walk_rate IS NOT NULL
                )
                OR (
                    plate_appearances > 0
                    AND (
                        walk_rate IS NULL
                        OR ABS(
                            walk_rate
                            - (walks::numeric / plate_appearances)
                        ) > {_RATE_TOLERANCE}
                    )
                )
                """
            )
        ).scalar_one()
    )
    rate_bound_violations = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE (
                    batting_average IS NOT NULL
                    AND (
                        batting_average < 0
                        OR batting_average > 1
                    )
                )
                OR (
                    on_base_percentage IS NOT NULL
                    AND (
                        on_base_percentage < 0
                        OR on_base_percentage > 1
                    )
                )
                OR (
                    slugging_percentage IS NOT NULL
                    AND (
                        slugging_percentage < 0
                        OR slugging_percentage > 4
                    )
                )
                OR (
                    ops IS NOT NULL
                    AND (ops < 0 OR ops > 5)
                )
                OR (
                    strikeout_rate IS NOT NULL
                    AND (
                        strikeout_rate < 0
                        OR strikeout_rate > 1
                    )
                )
                OR (
                    walk_rate IS NOT NULL
                    AND (walk_rate < 0 OR walk_rate > 1)
                )
                """
            )
        ).scalar_one()
    )
    negative_count_violations = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.player_season_batting
                WHERE {" OR ".join(f"{name} < 0" for name in _COUNT_METRICS)}
                """
            )
        ).scalar_one()
    )
    return {
        "game_batting_rows": game_batting_rows,
        "season_batting_rows": season_batting_rows,
        "duplicate_grains": duplicate_grains,
        "orphan_players": orphan_players,
        "orphan_seasons": orphan_seasons,
        "game_count_mismatches": game_count_mismatches,
        "count_metric_mismatches": count_metric_mismatches,
        "hit_component_violations": hit_component_violations,
        "batting_average_violations": batting_average_violations,
        "on_base_percentage_violations": on_base_percentage_violations,
        "slugging_percentage_violations": slugging_percentage_violations,
        "ops_violations": ops_violations,
        "strikeout_rate_violations": strikeout_rate_violations,
        "walk_rate_violations": walk_rate_violations,
        "rate_bound_violations": rate_bound_violations,
        "negative_count_violations": negative_count_violations,
    }


def _print_report(counts: dict[str, int]) -> None:
    print("Player Season Batting pipeline validation")
    print()
    print(f"game_batting_rows: {counts['game_batting_rows']}")
    print(f"season_batting_rows: {counts['season_batting_rows']}")
    print(f"duplicate_grains: {counts['duplicate_grains']}")
    print(f"orphan_players: {counts['orphan_players']}")
    print(f"orphan_seasons: {counts['orphan_seasons']}")
    print(f"game_count_mismatches: {counts['game_count_mismatches']}")
    print(f"count_metric_mismatches: {counts['count_metric_mismatches']}")
    print(f"hit_component_violations: {counts['hit_component_violations']}")
    print(f"batting_average_violations: {counts['batting_average_violations']}")
    print(
        "on_base_percentage_violations: "
        f"{counts['on_base_percentage_violations']}"
    )
    print(
        "slugging_percentage_violations: "
        f"{counts['slugging_percentage_violations']}"
    )
    print(f"ops_violations: {counts['ops_violations']}")
    print(f"strikeout_rate_violations: {counts['strikeout_rate_violations']}")
    print(f"walk_rate_violations: {counts['walk_rate_violations']}")
    print(f"rate_bound_violations: {counts['rate_bound_violations']}")
    print(f"negative_count_violations: {counts['negative_count_violations']}")
    print(f"pre_reload_row_count: {counts['pre_reload_row_count']}")
    print(f"reload_transformed_count: {counts['reload_transformed_count']}")
    print(f"reload_loaded_count: {counts['reload_loaded_count']}")
    print(f"reload_row_count: {counts['reload_row_count']}")


def _validate_pipeline(counts: dict[str, int], *, pre_reload) -> None:
    expected_zero = (
        "duplicate_grains",
        "orphan_players",
        "orphan_seasons",
        "game_count_mismatches",
        "count_metric_mismatches",
        "hit_component_violations",
        "batting_average_violations",
        "on_base_percentage_violations",
        "slugging_percentage_violations",
        "ops_violations",
        "strikeout_rate_violations",
        "walk_rate_violations",
        "rate_bound_violations",
        "negative_count_violations",
        "reload_snapshot_violations",
    )
    expected = {
        **{name: 0 for name in expected_zero},
        "reload_transformed_count": int(pre_reload["row_count"]),
        "reload_loaded_count": int(pre_reload["row_count"]),
        "reload_row_count": int(pre_reload["row_count"]),
    }
    mismatches = [
        f"{name}: expected {expected[name]}, got {counts[name]}"
        for name in expected
        if counts[name] != expected[name]
    ]
    if counts["season_batting_rows"] <= 0:
        mismatches.append(
            "season_batting_rows: expected > 0, "
            f"got {counts['season_batting_rows']}"
        )
    if mismatches:
        raise ValueError(
            "player_season_batting pipeline validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
