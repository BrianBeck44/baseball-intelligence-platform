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

SQLAlchemy ORM models are not used as an independent source of schema definition. PostgreSQL and Alembic remain authoritative for the physical database schema.

---

## 4. Module Responsibilities

The ingestion implementation is intentionally separated into focused modules.

```text
backend/
└── app/
    └── ingestion/
        ├── __init__.py
        ├── statcast.py
        ├── validation.py
        └── loader.py
```

### `statcast.py`

Orchestration layer.

Responsibilities:

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

Persistence layer.

Responsibilities:

* insert valid Statcast rows using SQLAlchemy Core;
* insert rejection records into `raw.ingestion_rejection`;
* update ingestion-batch information as required;
* use PostgreSQL conflict handling for idempotent source-key insertion.

The loader should not contain baseball-statistics calculations or source-row validation rules.

---

## 5. Ingestion Service Interface

V1 exposes the following service interface:

```python
ingest_statcast_file(
    file_path: Path,
    source_name: str,
    chunk_size: int = 10_000,
) -> IngestionResult
```

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

The loader is responsible for translating validated source data into database insert operations.

PostgreSQL remains responsible for enforcing database-level constraints, including:

* primary keys;
* foreign keys;
* NOT NULL constraints;
* CHECK constraints; and
* source-key uniqueness.

The ingestion code should not attempt to replace database integrity constraints with application-only checks.

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

The ingestion implementation should be tested at multiple levels.

### Unit tests

Focus on deterministic Python behavior such as:

* required-field validation;
* source-key validation;
* duplicate detection;
* filtering logic;
* rejection-reason assignment;
* count calculations.

### Integration tests

Use PostgreSQL to verify:

* successful insertion;
* foreign-key behavior;
* source-key uniqueness;
* `ON CONFLICT DO NOTHING`;
* ingestion-batch lineage;
* rejection persistence;
* transaction rollback behavior.

### End-to-end ingestion test

A representative Statcast sample should verify the complete workflow:

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

The existing small Statcast sample files can be used as fixtures for initial integration testing.

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
