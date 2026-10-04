"""Validate the player-season pitching analytics pipeline.

Read-only checks run against the currently persisted season pitching
rows. A temporary extract/transform/load is then executed in a
transaction that is always rolled back so production rows are not
changed.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.analytics.player_season_pitching_data import (
    get_player_season_pitching_games,
    transform_player_season_pitching,
)
from app.analytics.player_season_pitching_loader import (
    load_player_season_pitching,
)
from app.core.config import settings

_COUNT_METRICS = (
    "games",
    "batters_faced",
    "pitches",
    "hits_allowed",
    "home_runs_allowed",
    "walks",
    "hit_by_pitch",
    "strikeouts",
)
_SUM_METRICS = tuple(name for name in _COUNT_METRICS if name != "games")


def main() -> int:
    engine = create_engine(settings.database_url)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                pre_reload = _snapshot(connection)
                if int(pre_reload["row_count"]) <= 0:
                    raise ValueError(
                        "player_season_pitching pipeline validation failed:\n"
                        "  season_pitching_rows: expected > 0, got 0"
                    )

                counts = _collect_validations(connection)
                counts["pre_reload_row_count"] = int(pre_reload["row_count"])

                games = get_player_season_pitching_games(connection)
                rows = transform_player_season_pitching(connection, games)
                loaded_count = load_player_season_pitching(connection, rows)
                reload_snapshot = _snapshot(connection)

                counts["reload_transformed_count"] = len(rows)
                counts["reload_loaded_count"] = loaded_count
                counts["reload_row_count"] = int(reload_snapshot["row_count"])
                counts["reload_snapshot_violations"] = int(
                    reload_snapshot != pre_reload
                )

                _print_report(counts)
                _validate_pipeline(counts, pre_reload=pre_reload)
                print("Player Season Pitching pipeline validation succeeded.")
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
                        "player_season_pitching pipeline validation failed:\n"
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
                    COALESCE(SUM(batters_faced), 0) AS batters_faced,
                    COALESCE(SUM(pitches), 0) AS pitches,
                    COALESCE(SUM(hits_allowed), 0) AS hits_allowed,
                    COALESCE(SUM(home_runs_allowed), 0)
                        AS home_runs_allowed,
                    COALESCE(SUM(walks), 0) AS walks,
                    COALESCE(SUM(hit_by_pitch), 0) AS hit_by_pitch,
                    COALESCE(SUM(strikeouts), 0) AS strikeouts
                FROM analytics.player_season_pitching
                """
            )
        ).mappings().one()
    )


def _collect_validations(connection: Connection) -> dict[str, int]:
    game_pitching_rows = int(
        connection.execute(
            text("SELECT COUNT(*) FROM analytics.player_game_pitching")
        ).scalar_one()
    )
    season_pitching_rows = int(
        connection.execute(
            text("SELECT COUNT(*) FROM analytics.player_season_pitching")
        ).scalar_one()
    )
    duplicate_grains = int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT player_id, season_id
                    FROM analytics.player_season_pitching
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
                FROM analytics.player_season_pitching AS season
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
                FROM analytics.player_season_pitching AS season
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
                        pitching.pitcher_id AS player_id,
                        game.season_id,
                        COUNT(DISTINCT pitching.game_id) AS games
                    FROM analytics.player_game_pitching AS pitching
                    JOIN curated.game AS game
                      ON game.game_id = pitching.game_id
                    GROUP BY pitching.pitcher_id, game.season_id
                )
                SELECT COUNT(*)
                FROM analytics.player_season_pitching AS season
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
                        pitching.pitcher_id AS player_id,
                        game.season_id,
                        {", ".join(
                            f"SUM(pitching.{name}) AS {name}"
                            for name in _SUM_METRICS
                        )}
                    FROM analytics.player_game_pitching AS pitching
                    JOIN curated.game AS game
                      ON game.game_id = pitching.game_id
                    GROUP BY pitching.pitcher_id, game.season_id
                )
                SELECT COUNT(*)
                FROM analytics.player_season_pitching AS season
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
                FROM analytics.player_season_pitching
                WHERE home_runs_allowed > hits_allowed
                """
            )
        ).scalar_one()
    )
    negative_count_violations = int(
        connection.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM analytics.player_season_pitching
                WHERE {" OR ".join(f"{name} < 0" for name in _COUNT_METRICS)}
                """
            )
        ).scalar_one()
    )
    return {
        "game_pitching_rows": game_pitching_rows,
        "season_pitching_rows": season_pitching_rows,
        "duplicate_grains": duplicate_grains,
        "orphan_players": orphan_players,
        "orphan_seasons": orphan_seasons,
        "game_count_mismatches": game_count_mismatches,
        "count_metric_mismatches": count_metric_mismatches,
        "hit_component_violations": hit_component_violations,
        "negative_count_violations": negative_count_violations,
    }


def _print_report(counts: dict[str, int]) -> None:
    print("Player Season Pitching pipeline validation")
    print()
    print(f"game_pitching_rows: {counts['game_pitching_rows']}")
    print(f"season_pitching_rows: {counts['season_pitching_rows']}")
    print(f"duplicate_grains: {counts['duplicate_grains']}")
    print(f"orphan_players: {counts['orphan_players']}")
    print(f"orphan_seasons: {counts['orphan_seasons']}")
    print(f"game_count_mismatches: {counts['game_count_mismatches']}")
    print(f"count_metric_mismatches: {counts['count_metric_mismatches']}")
    print(f"hit_component_violations: {counts['hit_component_violations']}")
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
    if counts["season_pitching_rows"] <= 0:
        mismatches.append(
            "season_pitching_rows: expected > 0, "
            f"got {counts['season_pitching_rows']}"
        )
    if mismatches:
        raise ValueError(
            "player_season_pitching pipeline validation failed:\n"
            + "\n".join(f"  {mismatch}" for mismatch in mismatches)
        )


if __name__ == "__main__":
    sys.exit(main())
