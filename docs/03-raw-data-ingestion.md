# Project 3 — Raw Data Ingestion

## 1. Objective

Project 3 establishes the initial raw-data ingestion pipeline for the Baseball Intelligence Platform.

The goal is to acquire MLB Statcast pitch-level data from Baseball Savant, preserve the original source artifacts for reproducibility, validate and scope the data, and load the in-scope records into `raw.statcast_pitch`.

The raw layer is the first structured database representation of the external source. It is intentionally source-faithful and minimally transformed. Domain normalization and business rules belong in the staging and curated layers.

---

## 2. Initial Dataset

The initial Statcast dataset is:

* **League:** MLB
* **Source:** Baseball Savant Statcast CSV
* **Grain:** One row per pitch
* **Years:** 2022, 2023, 2024, 2025, and 2026 year-to-date
* **Game type:** Regular season only (`game_type = 'R'`)
* **Initial exclusions:** Spring Training, exhibition, All-Star, and postseason games

The initial dataset is intentionally limited to regular-season MLB data. Additional game types or historical coverage can be added later if the application requires them.

---

## 3. Source Artifact Strategy

Downloaded Statcast CSV files are retained locally under:

```text
data/raw/statcast/
```

The `data/` directory is excluded from Git because the downloaded source files are local data artifacts and may become large.

The downloaded CSV is treated as the source artifact. It should not be modified after download.

The source artifact and the database raw table serve different purposes:

* **Source artifact:** preserves the downloaded source exactly as received.
* **`raw.statcast_pitch`:** provides a structured database representation of the in-scope source records.

This distinction provides an auditable and reproducible path for rebuilding the raw database from the source data.

---

## 4. Ingestion Architecture

The initial ingestion flow is:

```text
Baseball Savant
       |
       v
Downloaded Statcast CSV
       |
       v
Validate / Scope
       |
       v
raw.statcast_pitch
       |
       v
staging
       |
       v
curated
```

The raw ingestion process should perform only the transformations necessary to validate the source and enforce the initial dataset scope.

Curated-domain transformations are intentionally deferred until later stages.

---

## 5. Download Strategy

Statcast data will be downloaded in manageable date-range chunks rather than through one very large request.

The process will begin with small samples to validate:

* source availability
* returned columns
* date-range behavior
* game types
* source-key uniqueness
* null patterns
* data types
* compatibility with the raw table

After validation, the same process can be applied to the complete 2022–2026 dataset.

The ingestion process should retain the source file associated with each download so that the data loaded into PostgreSQL can be traced back to its source artifact.

---

## 6. Scope Filtering

The Baseball Savant response can contain records outside the initial project scope.

For example, an early sample covering April 1–3, 2022 returned Spring Training records. A subsequent April 7–9, 2022 sample returned regular-season records.

The loader therefore must explicitly enforce:

```text
game_type = 'R'
```

Only regular-season records are loaded into `raw.statcast_pitch`.

Out-of-scope records are not modified or removed from the downloaded source artifact. They simply are not loaded into the structured raw table.

This keeps the source artifact complete while keeping the database dataset aligned with the project's defined scope.

---

## 7. Raw Table Grain and Identity

The raw table is:

```text
raw.statcast_pitch
```

Its grain is:

> One row represents one Statcast pitch.

The table uses an internal surrogate primary key:

```text
raw_statcast_pitch_id
```

The source natural key is:

```text
(game_pk, at_bat_number, pitch_number)
```

This source key is enforced with a unique constraint in PostgreSQL.

`sv_id` is preserved as a source field but is not used as the pitch identifier.

The table also records the ingestion batch associated with each loaded pitch through:

```text
ingestion_batch_id
```

---

## 8. Source Column Preservation

The initial Baseball Savant sample contains 119 source columns.

The raw table preserves the source contract rather than reducing it to only the fields currently needed by the curated model.

Important principles:

* Preserve all source columns represented by the initial Statcast contract.
* Preserve source field names where practical.
* Preserve source values without domain normalization.
* Preserve source NULLs.
* Preserve deprecated source fields rather than silently dropping them.
* Do not introduce curated foreign keys into the raw table.
* Do not replace source vocabulary with curated vocabulary in the raw layer.

Examples of source fields that remain raw include:

* `pitch_type`
* `pitch_name`
* `events`
* `description`
* `game_type`
* `stand`
* `p_throws`
* `launch_speed_angle`
* fielding-alignment fields
* `umpire`
* deprecated Statcast fields

The staging and curated layers are responsible for normalization and domain interpretation.

---

## 9. Source Vocabulary

Source vocabulary is preserved as supplied by Baseball Savant.

For example, the source contains pitch-type codes such as:

```text
CH, CS, CU, FC, FF, FS, KC, SI, SL, ST, SV
```

and source pitch names such as:

```text
4-Seam Fastball
Changeup
Curveball
Cutter
Knuckle Curve
Sinker
Slider
Slow Curve
Slurve
Split-Finger
Sweeper
```

The raw layer does not attempt to reconcile or normalize these values.

Curated reference tables are responsible for controlled domain vocabulary and canonical representations.

PostgreSQL ENUM types are not used for the raw source vocabulary.

---

## 10. NULL Handling

NULL values from the source are preserved as NULL in the raw table.

A column is not removed simply because it is currently sparsely populated or 100% NULL in the initial sample.

The raw schema represents the source contract rather than the observed population of a single sample.

This is particularly important for deprecated fields and newer Statcast tracking fields whose availability may vary by season or source coverage.

---

## 11. Ingestion Batch Tracking

Each ingestion operation is associated with a record in:

```text
raw.ingestion_batch
```

The batch table records:

* source name
* start time
* completion time
* status
* records received
* records loaded
* records rejected

The `raw.statcast_pitch.ingestion_batch_id` column references the corresponding ingestion batch.

This allows individual raw records to be associated with the ingestion operation that created them and provides a foundation for monitoring, auditing, and troubleshooting.

---

## 12. Validation

The ingestion process should validate the source before loading it.

Initial validation includes:

### Schema validation

Confirm that the expected Statcast source columns are present.

### Scope validation

Confirm that only:

```text
game_type = 'R'
```

records are eligible for loading.

### Source-key validation

Check for duplicate:

```text
(game_pk, at_bat_number, pitch_number)
```

combinations.

### Required-field validation

Confirm that required source identity fields are present, including:

* `game_pk`
* `at_bat_number`
* `pitch_number`

### Record-count reconciliation

Track:

```text
records_received
records_loaded
records_rejected
```

in the ingestion batch.

The detailed rejection strategy will be defined as the loader is implemented.

---

## 13. Data Type Principles

PostgreSQL types are selected deliberately rather than being generated directly from pandas dtype inference.

For example:

* MLB player identifiers remain integer identifiers even when pandas represents nullable values as floating-point.
* Physical Statcast measurements generally use `DOUBLE PRECISION`.
* Small discrete/count values use appropriately sized integer types where practical.
* Text source values remain text.
* NULLability follows the source and database requirements.

The raw database schema is authoritative for PostgreSQL types.

---

## 14. Auditability and Reproducibility

The ingestion design is intended to make the raw layer rebuildable.

The lineage is:

```text
Original Statcast CSV
        |
        v
Validation and scope filtering
        |
        v
raw.statcast_pitch
        |
        v
Staging transformations
        |
        v
Curated domain model
```

If the curated layer needs to be rebuilt, it should be possible to work from the raw layer.

If the raw layer itself needs to be rebuilt, the retained source artifacts provide the original input for the ingestion process.

This separation prevents downstream transformations from overwriting the original source representation.

---

## 15. Current Database Migration

The raw Statcast table is created through an Alembic migration:

```text
20388e16a800_create_raw_statcast_pitch_table.py
```

The migration creates:

```text
raw.statcast_pitch
```

with:

* `raw_statcast_pitch_id` identity primary key
* `ingestion_batch_id` foreign key to `raw.ingestion_batch`
* all 119 source columns
* required source-key fields
* unique constraint on `(game_pk, at_bat_number, pitch_number)`

Alembic is the authoritative source for the database schema.

---

## 16. Deferred Implementation Decisions

The following implementation details are intentionally not locked by this document:

* Python loader class/function structure
* pandas loading implementation
* PostgreSQL bulk-loading mechanism
* exact chunk size
* retry strategy
* logging implementation
* detailed rejected-record storage
* incremental versus full reload mechanics
* future cloud storage of source artifacts

These decisions will be made during ingestion implementation based on the project's requirements and operational needs.

---

## 17. Project 3 Milestone

At this point, the following design decisions are established:

* Initial Statcast dataset defined
* Source and scope defined
* Source artifact strategy defined
* Raw ingestion architecture defined
* Raw table grain and source key defined
* Source-column preservation policy defined
* NULL handling defined
* Batch tracking defined
* Initial validation requirements defined
* Raw Statcast PostgreSQL migration implemented

The next milestone is to design the **ingestion workflow and loader behavior** in enough detail to implement it safely and repeatably.
