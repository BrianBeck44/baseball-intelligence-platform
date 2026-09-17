# Ingestion Implementation

## 1. Purpose

This document records the implementation choices for the V1 Baseball Savant / Statcast ingestion pipeline.

The purpose of this document is to document not only what the ingestion pipeline does, but also how the implementation choices support the architectural and data-model decisions documented elsewhere in the project.

This document is intended to remain a living implementation record as the ingestion pipeline evolves.

---

## 2. Scope

V1 ingestion is responsible for loading Baseball Savant / Statcast CSV data into the raw PostgreSQL layer.

The ingestion service:

* accepts a local Statcast CSV file;
* processes the file in chunks;
* validates and filters source rows;
* records rejected rows for auditability;
* loads valid rows into `raw.statcast_pitch`;
* maintains ingestion-batch lineage;
* supports idempotent reprocessing of previously ingested data; and
* reports ingestion counts and final status.

Downloading Statcast data is outside the responsibility of the ingestion service.

---

## 3. Implementation Stack

V1 uses the following implementation technologies:

| Component                      | Technology                                    | Responsibility                                               |
| ------------------------------ | --------------------------------------------- | ------------------------------------------------------------ |
| CSV parsing / chunk processing | Pandas                                        | Read source data and perform chunk-level validation          |
| Database access                | SQLAlchemy Core                               | Bulk database persistence                                    |
| Database                       | PostgreSQL                                    | Persistence, constraints, source-key uniqueness, idempotency |
| Schema migrations              | Alembic                                       | Authoritative database migration history                     |
| Application configuration      | Pydantic Settings / environment configuration | Runtime configuration                                        |
| Backend language               | Python                                        | Ingestion service implementation                             |
| Automated testing              | pytest 8.4.2                                  | Validation, loader, and batch integration tests              |

SQLAlchemy ORM models are not used as an independent source of schema definition. PostgreSQL and Alembic remain authoritative for the physical database schema.

---

## 4. Module Responsibilities

The ingestion implementation is intentionally separated into focused modules.

Currently implemented:

```text
backend/
└── app/
    └── ingestion/
        ├── __init__.py
        ├── batch.py
        ├── validation.py
        └── loader.py
```

`statcast.py` is the planned orchestration module. It is not implemented yet.

### `statcast.py` (planned)

Orchestration layer.

When implemented, its responsibilities will be:

* coordinate the ingestion workflow;
* create and update the ingestion batch;
* read the source file in chunks;
* call validation functions;
* call persistence functions;
* maintain ingestion counters;
* manage chunk-level transaction boundaries;
* determine final ingestion status;
* return the `IngestionResult`.

The orchestration layer should not contain individual validation rules or SQL statements.

### `validation.py`

Validation and filtering layer.

Responsibilities:

* validate required source fields;
* validate source-key fields;
* identify duplicate source keys within the current processing chunk;
* identify rows outside V1 scope;
* return validation results and rejection information.

The validation layer should not perform database persistence.

### `loader.py`

Persistence layer for one validated Statcast chunk.

`backend/app/ingestion/loader.py` is implemented. It uses SQLAlchemy Core and receives an existing SQLAlchemy `Connection`. The caller owns the transaction boundary.

Responsibilities:

* normalize Pandas/NumPy values at the database boundary;
* insert valid Statcast rows into `raw.statcast_pitch`;
* attach `ingestion_batch_id` to each inserted pitch row;
* persist `RejectionRecord` objects into `raw.ingestion_rejection`;
* use PostgreSQL `INSERT ... ON CONFLICT DO NOTHING RETURNING` for idempotent source-key insertion.

The loader should not contain baseball-statistics calculations or source-row validation rules. It does not create or commit its own transaction. A fatal error is expected to be handled by the caller's transaction boundary.

### `batch.py`

Persistence layer for `raw.ingestion_batch`.

`backend/app/ingestion/batch.py` is implemented. It uses SQLAlchemy Core and receives an existing SQLAlchemy `Connection`. The caller owns the transaction boundary.

Responsibilities:

* create an ingestion batch in `RUNNING` status with all five counters initialized to `0`;
* update the five mutually exclusive counters during processing;
* complete a batch as `COMPLETED` with `completed_at` and final counters;
* fail a batch as `FAILED` with `completed_at` and current counters;
* raise if an update targets a nonexistent `ingestion_batch_id`.

The batch module does not read CSV files, validate source rows, load pitch rows, or calculate baseball statistics. It does not commit or roll back.

The persistence functions are:

```python
create_ingestion_batch(connection, source_name, started_at) -> int

update_ingestion_batch_counts(
    connection,
    ingestion_batch_id,
    *,
    records_received,
    records_filtered,
    records_rejected,
    records_skipped,
    records_loaded,
) -> None

complete_ingestion_batch(
    connection,
    ingestion_batch_id,
    *,
    completed_at,
    records_received,
    records_filtered,
    records_rejected,
    records_skipped,
    records_loaded,
) -> None

fail_ingestion_batch(
    connection,
    ingestion_batch_id,
    *,
    completed_at,
    records_received,
    records_filtered,
    records_rejected,
    records_skipped,
    records_loaded,
) -> None
```

---

## 5. Ingestion Service Interface

The planned orchestration interface, to be implemented in `statcast.py`, is:

```python
ingest_statcast_file(
    file_path: Path,
    source_name: str,
    chunk_size: int = 10_000,
) -> IngestionResult
```

This interface is not implemented yet.

### Inputs

* `file_path`: local path to the Statcast CSV file.
* `source_name`: identifier describing the source.
* `chunk_size`: number of physical source rows processed at a time.

The default chunk size is 10,000 rows.

### Result

The ingestion service returns an `IngestionResult` containing:

* ingestion batch ID;
* final status;
* records received;
* records filtered;
* records rejected;
* records skipped;
* records loaded; and
* an optional error message.

The result object may be expanded later if demonstrated operational needs require additional information.

---

## 6. Chunk-Based Processing

Statcast files are processed in chunks rather than loading the entire file into memory.

The default chunk size is:

```text
10,000 rows
```

Chunk processing provides:

* bounded memory usage;
* incremental database transactions;
* manageable validation units;
* clearer failure boundaries; and
* support for processing substantially larger source files.

The implementation should not assume that the complete Statcast dataset fits comfortably in memory.

---

## 7. Transaction Boundary

V1 uses one database transaction per processing chunk.

The intended behavior is:

```text
Chunk
  |
  +-- validation
  |
  +-- persistence
  |
  +-- commit
```

If a fatal error occurs while processing a chunk:

1. the current chunk transaction is rolled back;
2. previously committed chunks remain committed;
3. the ingestion batch is marked `FAILED`; and
4. processing stops.

This provides a balance between atomicity and practical processing of large source files.

---

## 8. Ingestion Batch Count Semantics

V1 uses five mutually exclusive record counters.

### `records_received`

Every physical data row read from the source CSV.

The header row is not counted.

### `records_filtered`

Rows that are outside the V1 ingestion scope.

For V1, a row is filtered when:

```text
game_type != 'R'
```

Filtered rows are not considered validation failures and are not written to `raw.ingestion_rejection`.

### `records_rejected`

In-scope rows that fail validation.

Examples include:

* missing required fields;
* invalid source-key values; and
* duplicate source keys within the current processing chunk.

Rejected rows are written to `raw.ingestion_rejection`.

### `records_skipped`

Valid rows whose source key already exists in PostgreSQL.

These rows are skipped through PostgreSQL's conflict handling and are not considered rejected.

### `records_loaded`

Rows that are actually inserted into `raw.statcast_pitch`.

A valid row that encounters an existing source key is therefore counted as `skipped`, not `loaded`.

### Completed-ingestion invariant

For a completed ingestion:

```text
records_received
=
records_filtered
+ records_rejected
+ records_skipped
+ records_loaded
```

This invariant provides a useful consistency check for ingestion results.

### Persistence

The five counters are persisted on `raw.ingestion_batch`:

* `records_received`
* `records_filtered`
* `records_rejected`
* `records_skipped`
* `records_loaded`

Alembic revision `e02a844d7b54` added `records_filtered` and `records_skipped` as `INTEGER NOT NULL DEFAULT 0`, with non-negative CHECK constraints.

### Status vocabulary

`raw.ingestion_batch.status` remains TEXT. PostgreSQL CHECK constraint `ck_ingestion_batch_status` restricts it to exactly:

```text
RUNNING
COMPLETED
FAILED
```

V1 does not use additional statuses or a PostgreSQL enum.

---

## 9. Validation Strategy

Validation is performed before database persistence.

V1 uses Pandas for chunk-level validation and duplicate detection.

Validation is concerned with source integrity and ingestion requirements rather than baseball-statistics calculations.

Examples of validation responsibilities include:

* required source fields are present;
* source-key fields are present and valid;
* source-key values have appropriate types/ranges;
* duplicate source keys within the current chunk are detected.

Validation errors are represented as structured rejection information so they can be persisted to the ingestion-rejection audit table.

---

## 10. Source-Key Strategy

The natural source key for a Statcast pitch is:

```text
(game_pk, at_bat_number, pitch_number)
```

The physical database enforces this with a unique constraint on:

```text
raw.statcast_pitch
    (game_pk, at_bat_number, pitch_number)
```

The database constraint is the final enforcement boundary for source uniqueness.

The `sv_id` field is preserved as source data but is not used as the V1 source identifier.

---

## 11. Duplicate Handling and Idempotency

V1 distinguishes between duplicates within the current processing chunk and records already present in PostgreSQL.

### Duplicate within the current chunk

If multiple rows in the same processing chunk have the same source key:

```text
(game_pk, at_bat_number, pitch_number)
```

the duplicate source rows are rejected.

They receive:

```text
DUPLICATE_SOURCE_KEY
```

as the rejection reason.

These rows are recorded in `raw.ingestion_rejection`.

### Source key already in PostgreSQL

If a valid row's source key already exists in `raw.statcast_pitch`, PostgreSQL handles the conflict using:

```sql
ON CONFLICT DO NOTHING
```

The existing database record is preserved.

The incoming row is counted as:

```text
records_skipped
```

It is not written to `raw.ingestion_rejection`.

This makes repeated ingestion of the same source data idempotent.

---

## 12. Ingestion Lineage

Every successfully inserted Statcast row contains:

```text
ingestion_batch_id
```

This foreign key references:

```text
raw.ingestion_batch.ingestion_batch_id
```

The value identifies the ingestion batch that originally inserted the row.

If a later ingestion encounters the same source key and PostgreSQL executes `ON CONFLICT DO NOTHING`, the existing row and its original `ingestion_batch_id` remain unchanged.

This preserves original ingestion lineage.

---

## 13. Rejection Audit

Rejected rows are persisted to:

```text
raw.ingestion_rejection
```

There is one rejection record per rejected source row.

The table contains:

* `ingestion_rejection_id`
* `ingestion_batch_id`
* `source_row_number`
* `rejection_reason`
* `source_key`
* `details`
* `raw_row`

### Rejection reasons

The initial controlled vocabulary is:

```text
MISSING_REQUIRED_FIELD
INVALID_SOURCE_KEY
DUPLICATE_SOURCE_KEY
```

The vocabulary is enforced with a PostgreSQL CHECK constraint.

### `source_row_number`

The source row number identifies the physical data row in the CSV.

The first data row is:

```text
1
```

The header row is excluded.

### `source_key`

When available, the source-key fields are stored as JSONB to make the rejected record easier to identify.

### `details`

Validation-specific diagnostic information is stored as JSONB.

If a row has multiple validation errors, they are represented in a single rejection record rather than creating multiple rejection records for the same source row.

### `raw_row`

The complete rejected source row is stored as JSONB.

This preserves the original rejected data for troubleshooting and future analysis.

Rejected rows are retained indefinitely in V1.

---

## 14. Filtering vs. Rejection

Filtering and rejection have intentionally different meanings.

A filtered row is outside the intended V1 scope and is therefore not considered bad source data.

For example:

```text
game_type != 'R'
```

is a V1 filtering condition.

A rejected row is within scope but fails a required ingestion or source-integrity rule.

For example:

```text
game_type = 'R'
```

with a missing required source-key field may be rejected.

This distinction keeps operational reporting meaningful.

---

## 15. Database Persistence

SQLAlchemy Core is used for bulk persistence.

`backend/app/ingestion/loader.py` persists one validated Statcast chunk.

The loader receives an existing SQLAlchemy `Connection`. The caller owns the transaction boundary. The loader does not begin, commit, or roll back the transaction.

Pandas/NumPy values are normalized at the database boundary before insert:

* missing Pandas/NumPy values are converted to `None` so PostgreSQL receives `NULL`;
* NumPy scalar values are converted to native Python values where necessary.

Valid rows are inserted into `raw.statcast_pitch`. Rejected rows are not inserted into `raw.statcast_pitch`; `RejectionRecord` objects are persisted into `raw.ingestion_rejection`.

Each inserted pitch row includes `ingestion_batch_id`.

PostgreSQL remains the final enforcement boundary for source-key uniqueness:

```text
(game_pk, at_bat_number, pitch_number)
```

PostgreSQL also remains responsible for:

* primary keys;
* foreign keys;
* NOT NULL constraints;
* CHECK constraints; and
* source-key uniqueness.

The ingestion code should not attempt to replace database integrity constraints with application-only checks.

A fatal error during persistence is expected to be handled by the caller's transaction boundary.

### Insert-and-Count Strategy

V1 uses PostgreSQL:

    INSERT ... ON CONFLICT DO NOTHING RETURNING

through SQLAlchemy Core to load validated Statcast rows into:

    raw.statcast_pitch

PostgreSQL remains the final enforcement boundary for source-key uniqueness.

The `RETURNING` result identifies rows that were actually inserted.

For each processing chunk:

    records_attempted = number of valid rows passed to the loader
    records_loaded    = number of rows returned by INSERT ... RETURNING
    records_skipped   = records_attempted - records_loaded

Therefore:

* `records_loaded` represents rows actually inserted into PostgreSQL;
* `records_skipped` represents valid rows whose source keys already existed in PostgreSQL; and
* a separate pre-insert existence query is not required.

### Duplicate Distinction

V1 distinguishes between duplicates detected during validation and source keys that already exist in PostgreSQL.

A duplicate source key within the current processing chunk:

    DUPLICATE_SOURCE_KEY

is a row-level validation rejection and is counted as:

    records_rejected

A valid source key that already exists in PostgreSQL is handled by:

    ON CONFLICT DO NOTHING

and is counted as:

    records_skipped

It is not recorded in `raw.ingestion_rejection`.

This distinction preserves the difference between invalid duplicate source data within the current input and an otherwise valid record being reprocessed from an already-ingested source.

### Transaction Boundary

Each processing chunk is handled within its own database transaction.

The transaction includes:

1. insertion of valid Statcast rows into `raw.statcast_pitch`;
2. insertion of rejection records into `raw.ingestion_rejection`; and
3. any other database changes required for that chunk.

If a fatal error occurs during the chunk:

    BEGIN
        ↓
    load valid rows
        ↓
    load rejection records
        ↓
    ERROR
        ↓
    ROLLBACK

The current chunk is rolled back, while previously committed chunks remain committed.

### Rationale

Using PostgreSQL's `ON CONFLICT DO NOTHING RETURNING` allows the database to enforce source-key uniqueness while also providing an authoritative way to determine which rows were actually inserted.

It avoids a separate pre-insert existence query and therefore avoids a race condition between checking whether a source key exists and attempting to insert it.

The resulting batch accounting remains internally consistent:

    records_received
        =
    records_filtered
        +
    records_rejected
        +
    records_skipped
        +
    records_loaded

Existing database duplicates are skipped, not rejected.

Application validation exists to provide earlier, clearer rejection handling and diagnostics.

---

## 16. Error Handling

V1 distinguishes expected row-level validation problems from fatal processing errors.

### Row-level validation failure

A row that fails validation:

* is rejected;
* is recorded in `raw.ingestion_rejection`;
* increments `records_rejected`; and
* does not terminate the ingestion.

### Fatal ingestion error

A fatal error such as an unexpected database or file-processing failure:

* stops ingestion immediately;
* rolls back the current chunk;
* preserves previously committed chunks;
* marks the ingestion batch `FAILED`; and
* records an appropriate error message.

The implementation should avoid silently swallowing unexpected exceptions.

---

## 17. Raw Data Preservation

The raw layer is intended to preserve source data as completely as practical.

The ingestion service therefore should not transform Statcast source data into baseball statistics during ingestion.

The ingestion pipeline is primarily responsible for:

```text
source data
    ↓
validation
    ↓
raw persistence
```

Baseball-specific statistics and analytical transformations belong in downstream curated or analytics processing.

---

## 18. Testing Strategy

The ingestion implementation is tested with pytest.

pytest 8.4.2 is included in `backend/requirements.txt`. No `pytest.ini`, `pyproject.toml`, or `conftest.py` has been introduced. Default pytest discovery is used from the `backend/` directory:

```text
backend/
└── tests/
    ├── __init__.py
    └── ingestion/
        ├── __init__.py
        ├── test_batch.py
        ├── test_loader.py
        └── test_validation.py
```

### Validation unit tests

Located in `tests/ingestion/test_validation.py`.

These tests do not require PostgreSQL. They construct small Pandas DataFrames in memory and exercise `validation.py` independently.

They cover:

* required-field validation;
* source-key validation;
* intra-chunk duplicate detection;
* filtering logic;
* rejection-reason assignment;
* `source_row_number` behavior;
* count calculations;
* JSON-safe conversion of Pandas/NumPy values.

There are currently 20 validation unit tests.

### Loader integration tests

Located in `tests/ingestion/test_loader.py`.

These tests use the real PostgreSQL database configured through `app.core.config.settings.database_url`. They do not mock PostgreSQL or SQLAlchemy persistence behavior.

They cover:

* successful insertion into `raw.statcast_pitch`;
* source-key uniqueness;
* `ON CONFLICT DO NOTHING RETURNING`;
* skip versus load counts;
* ingestion-batch lineage;
* rejection persistence into `raw.ingestion_rejection`;
* loading valid rows and rejections in the same chunk.

There are currently 6 loader integration tests.

PostgreSQL is the final enforcement boundary for source-key uniqueness, `ON CONFLICT` behavior, `RETURNING` behavior, foreign keys, and persistence. These behaviors are therefore verified against PostgreSQL rather than mocked.

### Batch persistence integration tests

Located in `tests/ingestion/test_batch.py`.

These tests use the real PostgreSQL database configured through `app.core.config.settings.database_url`. They do not mock PostgreSQL.

They cover:

* creating a `RUNNING` batch with all five counters initialized to `0`;
* updating the five counters without changing status;
* completing a batch as `COMPLETED` with `completed_at`;
* failing a batch as `FAILED` with `completed_at`;
* PostgreSQL rejection of an invalid status;
* PostgreSQL rejection of NULL for `records_filtered` and `records_skipped`;
* PostgreSQL rejection of a negative counter;
* a clear exception when updating a nonexistent `ingestion_batch_id`.

There are currently 8 batch persistence integration tests.

### Test isolation

Loader and batch integration tests do not depend on manually inserted sample data and do not hard-code `ingestion_batch_id` values.

Each loader test:

* creates its own `raw.ingestion_batch` row;
* uses unique test source keys that will not collide with sample Statcast data;
* uses the caller-owned transaction contract (`engine.begin()`);
* deletes `raw.statcast_pitch` and `raw.ingestion_rejection` rows before deleting the ingestion batch.

Each batch test creates its own `raw.ingestion_batch` row with a unique `source_name` and deletes that row after the assertion.

### Current test status

At this checkpoint:

* Validation tests: 20 passed
* Loader integration tests: 6 passed
* Batch persistence tests: 8 passed
* Total: 34 passed

These counts describe the current checkpoint. They are not a permanent test inventory.

### End-to-end ingestion test

An end-to-end test of the complete orchestration workflow remains planned until `statcast.py` is implemented:

```text
CSV
 ↓
chunk processing
 ↓
filtering
 ↓
validation
 ↓
rejection audit
 ↓
database insertion
 ↓
ingestion result
```

The existing small Statcast sample files can be used as fixtures for that later test.

---

## 19. Current Implementation Decisions

The following V1 decisions are considered locked unless a new requirement demonstrates the need to change them.

| Decision                       | V1 Choice                    |
| ------------------------------ | ---------------------------- |
| CSV processing                 | Pandas                       |
| Processing model               | Chunked                      |
| Default chunk size             | 10,000 rows                  |
| Database access                | SQLAlchemy Core              |
| Source uniqueness              | PostgreSQL unique constraint |
| Existing-source handling       | `ON CONFLICT DO NOTHING`     |
| Intra-chunk duplicate handling | Row-level rejection          |
| Transaction boundary           | One transaction per chunk    |
| Rejection storage              | `raw.ingestion_rejection`    |
| Rejection row retention        | Indefinite in V1             |
| Raw rejected row               | JSONB                        |
| Validation details             | JSONB                        |
| Source key in rejection        | JSONB                        |
| Ingestion lineage              | `ingestion_batch_id`         |
| Ingestion status vocabulary    | RUNNING / COMPLETED / FAILED |
| Batch persistence              | SQLAlchemy Core `batch.py`   |
| Loader transaction             | Caller-owned SQLAlchemy connection |
| Automated testing              | pytest                       |
| Downloading source files       | Outside ingestion service    |
| Baseball statistics            | Outside ingestion service    |

---

## 20. Future Considerations

The following are intentionally deferred until demonstrated requirements exist:

* automatic Statcast downloading;
* scheduling recurring ingestion jobs;
* cloud object storage;
* distributed ingestion;
* parallel chunk processing;
* advanced rejection analytics;
* JSONB indexing;
* additional rejection reason reference tables;
* materialized ingestion metrics;
* streaming ingestion;
* ingestion of additional source providers.

These should be introduced only when they provide a demonstrated benefit to the platform.

---

## 21. Relationship to Other Project Documentation

This document describes implementation choices.

Related documentation includes:

* `docs/01-data-strategy.md` — data-source and data-strategy decisions.
* `docs/02-physical-schema.md` — PostgreSQL physical schema decisions.
* `docs/03-ingestion-architecture.md` — ingestion architecture and service responsibilities.

The implementation documentation should be updated when a significant implementation choice changes.
