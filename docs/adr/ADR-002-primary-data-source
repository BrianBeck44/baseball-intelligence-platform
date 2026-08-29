# ADR-002: Primary Baseball Data Source — MLB Statcast / Baseball Savant

**Status:** Accepted
**Date:** 2026-08-29

## Context

The Baseball Intelligence Platform requires a baseball data source capable of supporting both traditional baseball statistics and deeper analytical use cases.

The project is intended to demonstrate data engineering, database design, advanced SQL, analytics, Python development, API development, and frontend engineering.

A simple season-level statistics dataset would be sufficient for basic player and team dashboards but would not provide enough granularity to demonstrate the full analytical capabilities envisioned for the platform.

The preferred data source should therefore provide:

* Pitch-level data
* Player and team identifiers
* Game information
* Pitch characteristics
* Pitch location
* Pitch outcomes
* Batted-ball information
* Historical data
* Advanced/expected metrics where available
* Programmatic access suitable for automated ingestion

## Decision

The Baseball Intelligence Platform will use **MLB Statcast data made available through Baseball Savant as its primary analytical data source**.

The project will initially use **pybaseball** as a Python acquisition library for retrieving Statcast data.

The architecture will treat pybaseball as an acquisition mechanism rather than as the canonical source of the data.

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

This abstraction will allow the ingestion layer to evolve independently of the acquisition library if necessary.

## Rationale

### 1. Pitch-level granularity

Statcast provides data at the pitch level, allowing the platform to model baseball events at a much deeper level than traditional player-season statistics.

This supports analytical relationships such as:

```text
Pitch
  ↓
Plate Appearance
  ↓
Game
  ↓
Player/Game
  ↓
Player/Season
```

This level of granularity is central to the project's analytical goals.

### 2. Rich analytical data

Statcast provides information that can support analysis involving:

* Pitch type
* Pitch velocity
* Pitch location
* Spin
* Release characteristics
* Batter/pitcher matchup
* Count
* Pitch outcome
* Batted-ball characteristics
* Launch speed
* Launch angle
* Expected statistics

This allows the platform to move beyond traditional box-score statistics.

### 3. Historical data

Statcast-related data provides substantial historical coverage, while recognizing that the available measurements and underlying tracking technologies have evolved over time.

The platform will account for differences in metric availability across historical periods rather than assuming all seasons contain identical measurements.

### 4. Strong fit for data engineering

The volume and granularity of Statcast data provide meaningful opportunities to demonstrate:

* Batch ingestion
* Historical backfills
* Incremental ingestion
* Data validation
* Deduplication
* Data normalization
* Schema evolution
* Data-quality monitoring
* Database indexing and optimization

### 5. Strong fit for advanced SQL

Pitch-level data creates opportunities for sophisticated SQL analysis involving:

* Common table expressions
* Window functions
* Conditional aggregation
* Rolling averages
* Ranking
* Percentile calculations
* Year-over-year comparisons
* Player comparisons
* Pitch-type analysis
* Situational analysis

This aligns directly with the project's goal of developing and demonstrating advanced SQL skills.

## Alternatives Considered

### Traditional Baseball Statistics Datasets

Traditional datasets provide useful historical player, team, and game statistics.

**Advantages:**

* Simple to understand
* Relatively small
* Easy to query
* Strong historical coverage

**Disadvantages:**

* Limited pitch-level information
* Limited tracking data
* Fewer opportunities for advanced analytics
* Less opportunity to demonstrate large-scale data ingestion and modeling

These datasets may be incorporated later as supplemental sources but will not serve as the primary analytical source.

### MLB APIs

MLB APIs can provide valuable information such as:

* Schedules
* Games
* Rosters
* Players
* Current game information

They may be incorporated as a secondary source, particularly for application features requiring current game or roster information.

They are not selected as the primary analytical source because Statcast provides the deeper pitch-level data required by the project's core analytical objectives.

### Commercial Baseball Data APIs

Commercial providers may provide high-quality data and APIs.

However, the additional cost and dependency on a commercial provider are not necessary for the initial project.

A commercial provider may be evaluated in the future if the platform requires capabilities unavailable through the selected sources.

## Acquisition Strategy

The initial ingestion architecture will use pybaseball to retrieve Statcast data.

However, the ingestion layer will be designed around our own internal interfaces rather than coupling the database directly to pybaseball.

Conceptually:

```text
External Data Source
        │
        ▼
Acquisition Adapter
        │
        ▼
Validation
        │
        ▼
Normalization
        │
        ▼
Raw Data
        │
        ▼
Core Data
        │
        ▼
Analytical Data
```

This allows the acquisition implementation to change without requiring a redesign of the entire platform.

## Historical Data Strategy

The initial system will perform a historical backfill for a defined range of seasons.

The exact starting season and historical scope will be determined during database and ingestion planning.

Historical metric availability will be explicitly considered during schema design and data validation.

The system should not assume that every Statcast field is populated for every historical season.

## Incremental Data Strategy

After the historical backfill, the platform should support incremental ingestion.

The intended future architecture is:

```text
Historical Backfill
       +
Daily Incremental Loads
       +
Data Validation
       +
Upsert / Deduplication
```

This will allow the project to evolve from a static analytical dataset into a continuously updated data platform.

## Consequences

### Positive

* Provides extremely rich baseball data.
* Enables pitch-level analytics.
* Creates meaningful data-engineering challenges.
* Provides substantial opportunities for advanced SQL.
* Supports interesting baseball intelligence features.
* Provides a realistic reason to implement a multi-layer data architecture.
* Creates a strong portfolio demonstration of data engineering and analytics.

### Negative

* Pitch-level data is significantly larger and more complex than traditional baseball statistics.
* Historical data may contain differences in field availability and measurement methodology.
* Ingestion will require more engineering than loading a simple CSV dataset.
* Large datasets will require thoughtful PostgreSQL indexing and query optimization.
* External data acquisition may be subject to availability, rate limits, or changes in upstream interfaces.

These challenges are considered acceptable because they directly contribute to the project's educational and portfolio objectives.

## Future Considerations

The platform may eventually incorporate additional sources for:

* Current game information
* Rosters
* Historical statistics
* Supplemental player information
* Data validation and cross-referencing

Additional sources will be introduced only when they provide a clear capability that the primary source does not adequately provide.

## Related Decisions

* **ADR-001:** Frontend Framework — React + TypeScript
* **ADR-003:** Database Architecture
* **ADR-004:** Data Ingestion Architecture
* **ADR-005:** FastAPI Application Architecture
