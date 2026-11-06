"""Rollback-only validation for analytics.player_season_ca_ops.

This script uses TEST_DATABASE_URL / baseball_intelligence_test only.
It never reads DATABASE_URL, never writes to baseball_intelligence, and
always rolls back validation writes.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.analytics.load_all import SeasonLoadResult
from app.analytics.player_season_ca_ops_data import (
    get_player_season_ca_ops_appearances,
    get_player_season_ca_ops_targets,
    transform_player_season_ca_ops,
)
from app.analytics.player_season_ca_ops_loader import load_player_season_ca_ops
from app.analytics.rebuild_validation import validate_player_season_ca_ops_load
from tests.db import REQUIRED_TEST_DATABASE_NAME, get_test_database_url


def main() -> int:
    engine = create_engine(get_test_database_url())
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                database_name = connection.execute(
                    text("SELECT current_database()")
                ).scalar_one()
                if database_name != REQUIRED_TEST_DATABASE_NAME:
                    raise RuntimeError(
                        "CA-OPS pipeline validation must use "
                        f"{REQUIRED_TEST_DATABASE_NAME}, not '{database_name}'."
                    )
                pre_reload = _snapshot(connection)
                batting_rows = _season_batting_row_count(connection)
                print(f"database: {database_name}")
                print(f"season_batting_rows: {batting_rows}")
                if batting_rows <= 0:
                    print("populated-data reconciliation: skipped")
                    print(
                        "reason: 0 eligible player_season_batting rows; "
                        "this is not formula validation"
                    )
                else:
                    counts = _run_pipeline(connection)
                    counts["pre_reload_row_count"] = int(pre_reload["row_count"])
                    counts["connected_database"] = database_name
                    _print_report(counts)
                    _validate_counts(counts, database_name=database_name)
                    print("populated-data reconciliation: succeeded")
                    print("Player Season CA-OPS pipeline validation succeeded.")
            except Exception:
                transaction.rollback()
                raise
            else:
                transaction.rollback()
                post_reload = _snapshot(connection)
                if post_reload != pre_reload:
                    raise ValueError(
                        "player_season_ca_ops pipeline validation failed:\n"
                        "  rollback did not restore the previous snapshot"
                    )
                print("rollback: succeeded")
                return 0
    finally:
        engine.dispose()


def _season_batting_row_count(connection: Connection) -> int:
    return int(
        connection.execute(
            text("SELECT COUNT(*) FROM analytics.player_season_batting")
        ).scalar_one()
    )


def _run_pipeline(connection: Connection) -> dict[str, object]:
    appearances = get_player_season_ca_ops_appearances(connection)
    targets = get_player_season_ca_ops_targets(connection)
    rows = transform_player_season_ca_ops(connection, appearances, targets)
    loaded_count = load_player_season_ca_ops(connection, rows)
    result = SeasonLoadResult(
        extracted_count=len(appearances),
        transformed_count=len(rows),
        loaded_count=loaded_count,
    )
    validate_player_season_ca_ops_load(connection, result)
    return _collect_validations(connection, result)


def _snapshot(connection: Connection) -> dict[str, object]:
    row = connection.execute(
        text(
            """
            SELECT
                COUNT(*) AS row_count,
                COALESCE(SUM(plate_appearances), 0) AS plate_appearances,
                COUNT(*) FILTER (WHERE ca_ops IS NULL) AS null_ca_ops_rows,
                COALESCE(MAX(created_at), TIMESTAMPTZ 'epoch') AS max_created_at
            FROM analytics.player_season_ca_ops
            """
        )
    ).mappings().one()
    return dict(row)


def _collect_validations(
    connection: Connection,
    result: SeasonLoadResult,
) -> dict[str, object]:
    totals = connection.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM analytics.player_season_batting)
                    AS batting_rows,
                (SELECT COUNT(*) FROM analytics.player_season_ca_ops)
                    AS ca_ops_rows,
                (SELECT COUNT(*) FROM curated.plate_appearance)
                    AS plate_appearances,
                COUNT(*) FILTER (
                    WHERE batting.ops IS DISTINCT FROM ca_ops.observed_ops
                ) AS observed_ops_mismatches,
                COUNT(*) FILTER (
                    WHERE batting.player_id IS NULL
                ) AS extra_ca_ops_rows,
                COUNT(*) FILTER (
                    WHERE ca_ops.player_id IS NULL
                ) AS missing_ca_ops_rows,
                COUNT(*) FILTER (
                    WHERE ca_ops.ca_ops IS NULL
                ) AS null_ca_ops_rows
            FROM analytics.player_season_batting AS batting
            FULL OUTER JOIN analytics.player_season_ca_ops AS ca_ops
              ON ca_ops.player_id = batting.player_id
             AND ca_ops.season_id = batting.season_id
            """
        )
    ).mappings().one()
    return {
        "extracted_count": result.extracted_count,
        "transformed_count": result.transformed_count,
        "loaded_count": result.loaded_count,
        "batting_rows": int(totals["batting_rows"]),
        "ca_ops_rows": int(totals["ca_ops_rows"]),
        "plate_appearances": int(totals["plate_appearances"]),
        "observed_ops_mismatches": int(totals["observed_ops_mismatches"]),
        "extra_ca_ops_rows": int(totals["extra_ca_ops_rows"]),
        "missing_ca_ops_rows": int(totals["missing_ca_ops_rows"]),
        "null_ca_ops_rows": int(totals["null_ca_ops_rows"]),
    }


def _print_report(counts: dict[str, object]) -> None:
    for name, value in counts.items():
        print(f"{name}: {value}")


def _validate_counts(
    counts: dict[str, object],
    *,
    database_name: str,
) -> None:
    failures: list[str] = []
    if database_name != REQUIRED_TEST_DATABASE_NAME:
        failures.append(
            "connected_database: expected "
            f"{REQUIRED_TEST_DATABASE_NAME}, got {database_name}"
        )
    if int(counts["extracted_count"]) != int(counts["plate_appearances"]):
        failures.append(
            "extracted_count: expected "
            f"{counts['plate_appearances']}, got {counts['extracted_count']}"
        )
    if int(counts["transformed_count"]) != int(counts["batting_rows"]):
        failures.append(
            "transformed_count: expected "
            f"{counts['batting_rows']}, got {counts['transformed_count']}"
        )
    if int(counts["loaded_count"]) != int(counts["batting_rows"]):
        failures.append(
            "loaded_count: expected "
            f"{counts['batting_rows']}, got {counts['loaded_count']}"
        )
    if int(counts["ca_ops_rows"]) != int(counts["batting_rows"]):
        failures.append(
            "ca_ops_rows: expected "
            f"{counts['batting_rows']}, got {counts['ca_ops_rows']}"
        )
    for name in (
        "observed_ops_mismatches",
        "extra_ca_ops_rows",
        "missing_ca_ops_rows",
    ):
        if int(counts[name]) != 0:
            failures.append(f"{name}: expected 0, got {counts[name]}")
    if failures:
        raise ValueError(
            "player_season_ca_ops pipeline validation failed:\n"
            + "\n".join(f"  {failure}" for failure in failures)
        )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Player Season CA-OPS pipeline validation failed: {exc}")
        raise
