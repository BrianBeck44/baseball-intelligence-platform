# Historical Season Backfill Runbook

This runbook describes how to acquire Statcast data for one MLB season,
ingest it into the raw layer, rebuild curated data, rebuild analytics,
and validate the results.

Use this workflow one season at a time. The worked example below
backfills **2024** after 2022 and 2023 have already been loaded.

## 1. Scope and safety rules

-   Run shell commands from the repository's `backend/` directory.
-   Target the **development** database, `baseball_intelligence`. Do not
    run the backfill against `baseball_intelligence_test`.
-   Preserve previously acquired raw files and existing seasons.
-   Do not delete database records to make room for a new season.
-   Stop if any command fails. Investigate the error before proceeding.
-   `load_curated.py` rebuilds curated data from the raw data available
    to the project; it is not limited to the year in the most recent
    acquisition.
-   `load_analytics.py` rebuilds the analytics datasets from curated
    data. Run it only after curated loading and validation succeed.
-   The acquisition date range includes extra days around the regular
    season. The ingestion pipeline filters records according to its
    configured game-type rules, so the exact number of games with
    Statcast coverage may differ from the full MLB schedule.

Before starting, confirm your shell is in `backend/` and the virtual
environment exists at `../.venv/`.

Optional database-target check (run from `backend/`):

``` bash
PYTHONPATH=. ../.venv/bin/python -c "from sqlalchemy import create_engine, text; from app.core.config import settings; engine = create_engine(settings.database_url); print(engine.connect().execute(text('SELECT current_database()')).scalar())"
```

If your project exposes its database setting under a different
configuration attribute, use the project's established configuration
method. Confirm the result is `baseball_intelligence` before running
loaders.

## 2. Acquire raw Statcast data

For the 2024 example, run from `backend/`:

``` bash
PYTHONPATH=. ../.venv/bin/python scripts/acquire_statcast_range.py 2024-03-20 2024-11-06
```

The acquisition script writes CSV files under:

``` text
../data/raw/statcast/acquired/
```

Review the output and confirm the expected `statcast_2024-*.csv` files
exist before ingesting them.

ls -1 ../data/raw/statcast/acquired/statcast_2026-*.csv | wc -l

## 3. Ingest all 2024 raw files

This loop ingests each matching CSV and stops immediately if an
ingestion command fails. It also fails if no matching files are found.

``` bash
matched=0
for f in ../data/raw/statcast/acquired/statcast_2024-*.csv; do
  [ -f "$f" ] || continue
  matched=1
  echo "Ingesting $f"
  PYTHONPATH=. ../.venv/bin/python scripts/ingest_statcast.py "$f" || {
    echo "ERROR: Ingestion failed for $f"
    exit 1
  }
done

if [ "$matched" -eq 0 ]; then
  echo "ERROR: No 2024 Statcast CSV files found."
  exit 1
fi
```

Do not continue if ingestion fails. A file can be retried after
investigating the error; ingestion uses the project's natural-key
handling to avoid duplicating already-loaded records.

## 4. Load reference data

Run the reference-data loader. It is designed to be repeatable:

``` bash
PYTHONPATH=. ../.venv/bin/python scripts/load_reference_data.py
```

Confirm it reports success before continuing.

## 5. Load curated data

``` bash
PYTHONPATH=. ../.venv/bin/python scripts/load_curated.py
```

This loader processes the raw data available across seasons. Allow it to
finish; it may make external MLB Stats API requests and process a
substantial amount of data.

If it fails, stop and investigate the traceback. The curated load is
transactional; verify database state rather than assuming a failed
command partially loaded data.

## 6. Validate curated game counts

Run this SQL in your PostgreSQL client connected to the development
database:

``` sql
SELECT
    s.season_year,
    COUNT(g.game_id) AS games
FROM curated.season s
LEFT JOIN curated.game g
    ON g.season_id = s.season_id
GROUP BY s.season_year
ORDER BY s.season_year;
```

For the current project baseline, 2022 and 2023 each have 2,430
regular-season games. After a successful 2024 backfill, 2024 should also
be populated and should be close to the expected full-season schedule.

Do not treat 2,430 as proof that every game has complete Statcast pitch
coverage. If a season's count is unexpected, investigate before
continuing.

## 7. Rebuild analytics

Only after curated loading succeeds and the curated game counts have
been reviewed, run:

``` bash
PYTHONPATH=. ../.venv/bin/python scripts/load_analytics.py
```

Wait for the loader to report that aggregate validation and the
transaction commit succeeded. If it fails, stop and investigate before
rerunning.

## 8. Validate analytics by season

Run this SQL in PostgreSQL. The separate common table expressions
aggregate each dataset before joining, avoiding row multiplication from
joining several fact tables directly.

``` sql
WITH game_counts AS (
    SELECT season_id, COUNT(*) AS games
    FROM curated.game
    GROUP BY season_id
),
batting_counts AS (
    SELECT
        g.season_id,
        COUNT(*) AS batting_rows
    FROM analytics.player_game_batting pgb
    JOIN curated.game g
        ON g.game_id = pgb.game_id
    GROUP BY g.season_id
),
trend_counts AS (
    SELECT season_id, COUNT(*) AS trend_rows
    FROM analytics.player_performance_trends
    GROUP BY season_id
)
SELECT
    s.season_year,
    COALESCE(g.games, 0) AS games,
    COALESCE(b.batting_rows, 0) AS batting_rows,
    COALESCE(t.trend_rows, 0) AS trend_rows
FROM curated.season s
LEFT JOIN game_counts g
    ON g.season_id = s.season_id
LEFT JOIN batting_counts b
    ON b.season_id = s.season_id
LEFT JOIN trend_counts t
    ON t.season_id = s.season_id
ORDER BY s.season_year;
```

### Known-good baseline before 2024

  Season     Curated games   Player-game batting rows   Trend rows
  -------- --------------- -------------------------- ------------
  2022               2,430                     48,327       48,327
  2023               2,430                     48,766       48,766
  2024                   0                          0            0

After the 2024 backfill:

-   Confirm the 2022 and 2023 counts remain unchanged.
-   Confirm 2024 has populated game, batting, and trend counts.
-   Confirm batting and trend row counts match for each loaded season.
-   Investigate unexpected zero counts or differences before backfilling
    another season.

The baseline values above are observations from the current development
database, not universal constants. If the raw data scope changes,
document the new validated baseline and why it changed.

## 9. Reuse the workflow for another season

For a later season, update both the acquisition dates and the file glob
in the ingestion loop. For example, the acquisition command for 2025 is:

``` bash
PYTHONPATH=. ../.venv/bin/python scripts/acquire_statcast_range.py 2025-03-20 2025-11-06
```

Change the ingestion glob to `statcast_2025-*.csv`, then repeat the
reference-data load, curated load, curated validation, analytics
rebuild, and analytics validation in order. Backfill only one season at
a time.

For 2026, choose a date range appropriate to the season's completion and
the intended coverage; do not assume the season's data is final before
the source has published it.

## 10. Troubleshooting checklist

If a loader fails:

1.  Stop the workflow at the failed step.
2.  Keep the full traceback and command output.
3.  Identify whether the error is due to an unrecognized reference
    value, incomplete raw acquisition, database configuration, or a
    transformation/validation issue.
4.  Add or correct reference mappings only after verifying the source
    semantics. Keep fail-fast behavior for genuinely unsupported values.
5.  Add regression tests for code fixes and run the relevant tests
    before retrying the loader.
6.  Verify curated and analytics counts after any retry. Do not delete
    earlier seasons as a workaround.

## Backfill completion checklist

-   [ ] Confirmed development database target.
-   [ ] Acquired raw files for one season.
-   [ ] Ingested every matching file successfully.
-   [ ] Loaded reference data successfully.
-   [ ] Loaded curated data successfully.
-   [ ] Validated curated game counts and preserved earlier seasons.
-   [ ] Rebuilt analytics successfully.
-   [ ] Validated batting/trend counts by season.
-   [ ] Recorded any baseline changes or data-coverage caveats.
