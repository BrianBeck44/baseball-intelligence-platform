# Baseball Intelligence Platform — Data Strategy

**Document:** 01-data-strategy.md
**Status:** Accepted
**Date:** 2026-08-29
**Related ADRs:** ADR-002 — Primary Baseball Data Source

---

## 1. Purpose

This document defines the initial data strategy for the Baseball Intelligence Platform.

The strategy establishes:

* Primary data sources
* Historical data scope
* Data granularity
* Data storage layers
* Ingestion strategy
* Data quality principles
* Data retention
* Data lineage
* Cloud strategy

The purpose is to provide a stable foundation for database architecture, data pipeline development, analytics, and API development.

Implementation-specific decisions such as table schemas, indexes, partitioning, and database keys will be addressed during **Project 1 — Database Architecture & Design**.

---

# 2. Data Objectives

The data architecture must support three levels of baseball analysis.

## 2.1 Traditional Baseball Statistics

The platform should support common baseball information including:

* Players
* Teams
* Games
* Batting statistics
* Pitching statistics
* Player performance over time
* Team performance over time

## 2.2 Advanced Baseball Analytics

The data architecture should support calculations involving metrics such as:

* wOBA
* xwOBA
* Barrel Rate
* Hard-Hit Rate
* Whiff Rate
* Chase Rate
* Pitch-type performance
* Pitch-location analysis
* Batted-ball analysis

## 2.3 Baseball Intelligence

The platform should eventually support higher-level analytical questions such as:

* What pitches is a particular hitter most vulnerable to?
* How has a pitcher's pitch arsenal changed over time?
* Is a player's improvement supported by underlying contact-quality changes?
* How does a player's performance compare with similar players?
* What underlying metrics explain changes in traditional statistics?

The data architecture should preserve sufficient detail to answer new analytical questions without requiring repeated retrieval of historical source data.

---

# 3. Primary Data Source

The primary analytical data source will be **MLB Statcast data made available through Baseball Savant**.

The decision is documented in:

**ADR-002 — Primary Baseball Data Source**

Statcast was selected because it provides pitch-level data and rich tracking information suitable for advanced baseball analysis.

The project will initially use **pybaseball** as a Python acquisition library for retrieving Statcast data.

pybaseball is considered an acquisition mechanism rather than the canonical source of the data.

The architecture is therefore:

```text
MLB / Baseball Savant
        │
        ▼
   pybaseball
        │
        ▼
Our Ingestion Pipeline
        │
        ▼
    PostgreSQL
```

The ingestion architecture will be designed so that the acquisition mechanism can be replaced or supplemented in the future without requiring a redesign of the entire platform.

---

# 4. Initial Historical Scope

The initial historical scope will be:

**2022 through 2026**

The 2022–2025 seasons will provide completed historical seasons.

The 2026 season will represent the current/in-progress season and will provide an opportunity to develop incremental ingestion capabilities.

The initial model will therefore support:

```text
Historical Backfill
2022
2023
2024
2025

        +

Current Season
2026
```

The ingestion architecture should allow additional seasons to be added later without requiring fundamental architectural changes.

The project will not initially attempt to ingest the entire available Statcast historical archive.

---

# 5. Data Granularity

The fundamental raw data grain will be:

> **One row represents one pitch event.**

This pitch-level record will serve as the atomic event from which higher-level baseball information can be derived.

Conceptually:

```text
Pitch
  │
  ▼
Plate Appearance
  │
  ▼
Game
  │
  ├── Player/Game
  │
  └── Team/Game
          │
          ▼
       Season
```

This grain will allow the platform to support both traditional statistics and detailed pitch-level analytics.

The exact database keys and relationships will be determined during Project 1.

---

# 6. Data Layer Architecture

The platform will use three logical data layers:

```text
RAW
 │
 ▼
CORE
 │
 ▼
ANALYTICAL
```

## 6.1 RAW Layer

The RAW layer will preserve source data as close as practical to the form received from the external data source.

Primary purposes:

* Preserve source information
* Support reproducibility
* Allow downstream transformations to be rebuilt
* Provide a historical record of ingested data
* Simplify debugging and data-quality investigation

The raw Statcast dataset will have a grain of one row per pitch.

Raw data should not be unnecessarily transformed before being persisted.

---

## 6.2 CORE Layer

The CORE layer will contain cleaned and normalized entities used throughout the platform.

Potential entities include:

```text
Players
Teams
Games
Venues
Pitches
Plate Appearances
```

The exact schema will be designed during Project 1.

The CORE layer should represent the platform's internal understanding of the baseball data rather than simply mirror the external source schema.

---

## 6.3 ANALYTICAL Layer

The ANALYTICAL layer will contain derived datasets optimized for analytics and application use.

Potential analytical datasets include:

```text
Player/Game Statistics
Player/Season Statistics
Team/Game Statistics
Team/Season Statistics
Pitch-Type Analysis
Pitching Analysis
Hitting Analysis
Trend Metrics
```

The analytical layer will allow complex transformations to be performed ahead of API requests rather than requiring every user request to reconstruct complex calculations.

---

# 7. Raw Data Preservation

Raw source data will be preserved before significant transformation.

The principle is:

```text
External Source
      │
      ▼
   Preserve
      │
      ▼
Transform
```

This allows analytical models to be rebuilt if:

* A calculation is discovered to be incorrect
* A business rule changes
* A new metric is introduced
* The analytical schema changes
* A source field becomes useful for a new analysis

The initial historical raw dataset will be retained.

---

# 8. Ingestion Strategy

The initial ingestion architecture will use batch processing.

The initial historical process will perform a backfill of the 2022–2026 data.

Conceptually:

```text
Statcast
   │
   ▼
Acquire
   │
   ▼
Validate
   │
   ▼
Load RAW
   │
   ▼
Transform
   │
   ▼
CORE
   │
   ▼
ANALYTICAL
```

After the historical backfill, the system should support incremental ingestion for the active 2026 season.

The intended long-term model is:

```text
Historical Backfill
        +
Incremental Loads
        +
Validation
        +
Upsert / Deduplication
```

---

# 9. Incremental Ingestion

The system will use incremental ingestion after the initial historical backfill.

The goal is to avoid repeatedly downloading and processing the entire dataset.

The conceptual process is:

```text
Last Successful Ingestion
          │
          ▼
Determine Required Data
          │
          ▼
Acquire New / Updated Records
          │
          ▼
Validate
          │
          ▼
Insert / Update
```

The exact implementation will be determined during Project 2 — Data Ingestion Pipeline.

---

# 10. Idempotency and Duplicate Handling

The ingestion process should be idempotent.

> Running the same ingestion operation multiple times should result in the same final database state.

The system must therefore prevent duplicate pitch records from being created when:

* A job is accidentally executed twice
* A date range overlaps a previous ingestion
* An ingestion job is retried
* Historical data is reprocessed

The appropriate business/natural key for a pitch will be determined during database design.

Database constraints should ultimately provide an additional layer of protection against duplicate records.

---

# 11. Source Corrections

The system must account for the possibility that previously ingested source data can change.

For example:

```text
Initial ingestion
Pitch X → 94.2 mph

Later source update
Pitch X → 94.8 mph
```

The ingestion architecture should therefore support upserts or equivalent correction mechanisms.

Conceptually:

```text
New record
    → INSERT

Existing record with changed values
    → UPDATE

Existing unchanged record
    → NO ACTION
```

This will prevent the system from assuming that previously ingested records are permanently immutable.

---

# 12. Data Quality Strategy

Data quality will be validated at multiple levels.

## 12.1 Structural Validation

Verify that required fields and expected source structures are present.

Examples:

```text
game_id
game_date
pitcher_id
batter_id
pitch_number
```

## 12.2 Referential Validation

Verify relationships between entities.

For example:

```text
pitch.pitcher_id
       │
       ▼
players.player_id
```

## 12.3 Business/Data Validation

Validate values against reasonable expectations.

Examples:

```text
pitch_number > 0
release_speed > 0
```

Additional rules will be developed as the source data and analytical requirements become better understood.

---

# 13. NULL and Missing Data Strategy

Missing values will be preserved as NULL where appropriate.

The system will not automatically convert missing values into zero.

For example:

```text
launch_speed = NULL
```

does not necessarily mean:

```text
launch_speed = 0
```

A NULL value may indicate that:

* The metric was not applicable
* The metric was not recorded
* The metric was not available for that historical period
* The source did not provide the measurement

Historical metric availability will therefore be considered during analytical calculations.

---

# 14. Historical Metric Availability

The project will not assume that every Statcast field is populated consistently across all historical seasons.

Statcast measurement technology and available metrics have evolved over time.

The data model and analytical calculations must therefore account for:

* Fields unavailable during earlier periods
* Changes in measurement methodology
* Additional metrics introduced over time
* NULL values caused by historical limitations

Analytical documentation should identify important limitations when historical comparisons could be misleading.

---

# 15. Data Types

The CORE and ANALYTICAL layers will use appropriate PostgreSQL data types rather than representing all source values as strings.

Examples may include:

```text
game_date       → DATE
pitch_number    → INTEGER
release_speed   → NUMERIC
launch_angle    → NUMERIC
player_id       → appropriate identifier type
```

Exact PostgreSQL data types will be determined during Project 1.

---

# 16. Time Handling

The platform will distinguish between:

* Baseball event time
* Game date
* Data ingestion time

Where timestamps are available, they should be stored consistently.

Ingestion metadata should allow the system to determine when data was retrieved independently of when the baseball event occurred.

This distinction will support:

* Incremental ingestion
* Troubleshooting
* Data lineage
* Source corrections
* Pipeline monitoring

---

# 17. Data Lineage

The platform should provide traceability from analytical results back toward the underlying source data.

Conceptually:

```text
External Source
      │
      ▼
Raw Record
      │
      ▼
Transformation
      │
      ▼
Analytical Dataset
      │
      ▼
API
      │
      ▼
Frontend
```

The goal is to make it possible to understand where an analytical result originated and how it was transformed.

A full enterprise data-lineage platform is not required for the initial implementation.

Metadata, database structure, transformation code, and documentation will provide the initial lineage mechanism.

---

# 18. Data Retention

The initial historical dataset will be retained in the RAW layer.

The project will prioritize:

* Reproducibility
* Analytical flexibility
* Debugging
* Historical analysis

over aggressive storage optimization.

Additional retention policies may be introduced if the platform grows substantially.

---

# 19. Extensibility

The internal data model should not become tightly coupled to the schema of Baseball Savant.

The intended architecture is:

```text
                 Acquisition Sources
                         │
             ┌───────────┴───────────┐
             │                       │
       Baseball Savant          Future Source
             │                       │
             └───────────┬───────────┘
                         ▼
                  Ingestion Layer
                         │
                         ▼
                   Internal Model
```

This will allow future supplemental sources to be incorporated when they provide meaningful additional capabilities.

Potential future sources may provide:

* Current game information
* Rosters
* Supplemental player information
* Historical statistics
* Data validation
* Cross-reference information

Additional sources will only be introduced when they provide a clear benefit.

---

# 20. Development Environment

PostgreSQL will initially run locally during development.

The expected development architecture is:

```text
Developer Machine
       │
       ▼
Docker
       │
       ▼
PostgreSQL
```

This avoids unnecessary cloud infrastructure costs during early development and allows the database architecture to evolve rapidly.

---

# 21. Cloud Strategy

AWS will not be required during the initial development phase.

Cloud infrastructure will be introduced only after the platform has sufficient functionality to justify deployment.

The eventual architecture may include:

```text
AWS
 │
 ├── PostgreSQL
 ├── FastAPI
 ├── Data Pipeline
 └── React Application
```

The exact AWS services will be evaluated later.

Cloud cost will be treated as an architectural consideration rather than assuming that every development component must immediately run in the cloud.

---

# 22. Initial Data Architecture

The initial strategy can be summarized as:

```text
                   MLB Statcast
                        │
                        ▼
                   pybaseball
                        │
                        ▼
               Acquisition Layer
                        │
                        ▼
                 Validation
                        │
                        ▼
                ┌───────────────┐
                │      RAW      │
                │               │
                │ 1 row / pitch │
                └───────┬───────┘
                        │
                        ▼
                 Transformation
                        │
                        ▼
                ┌───────────────┐
                │     CORE      │
                │               │
                │ Players       │
                │ Teams         │
                │ Games         │
                │ Pitches       │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │  ANALYTICAL   │
                │               │
                │ Player Stats  │
                │ Team Stats    │
                │ Metrics       │
                │ Trends        │
                └───────────────┘
```

---

# 23. Initial Data Strategy Decisions

| Decision              | Selection                                      |
| --------------------- | ---------------------------------------------- |
| Primary source        | MLB Statcast / Baseball Savant                 |
| Acquisition           | pybaseball initially                           |
| Historical scope      | 2022–2026                                      |
| Development database  | Local PostgreSQL                               |
| Raw grain             | One row per pitch                              |
| Raw data preservation | Yes                                            |
| Data layers           | RAW → CORE → ANALYTICAL                        |
| Initial ingestion     | Batch                                          |
| Future ingestion      | Incremental                                    |
| Duplicate strategy    | Idempotent ingestion                           |
| Source corrections    | Upsert/update support                          |
| Missing data          | Preserve NULL semantics                        |
| Data quality          | Structural + referential + business validation |
| Retention             | Retain initial historical raw data             |
| Cloud                 | AWS later                                      |
| Supplemental sources  | Add only when justified                        |

---

# 24. Next Steps

The next phase is:

## Project 1 — Database Architecture & Design

Project 1 will translate this data strategy into a concrete relational model.

It will address:

* Entity identification
* Table grain
* Relationships
* Primary keys
* Foreign keys
* Natural/business keys
* Constraints
* Data types
* Normalization
* Indexing
* Raw table design
* Core table design
* Analytical table design
* Database migrations

The most important first question will be:

> **What entities and relationships do we need to represent the baseball domain correctly?**

The database design will be driven by the data strategy documented here rather than by the requirements of the frontend.
