# Baseball Intelligence Platform — Physical Schema

## 1. Purpose

This document defines the physical PostgreSQL schema for the Baseball Intelligence Platform.

Project 1 established the baseball domain model and entity grains. Project 2 translates that logical model into a physical PostgreSQL design.

The physical schema is designed around the following priorities:

- Preserve authoritative source data where appropriate.
- Avoid unnecessary duplication.
- Maintain clear table grain.
- Enforce important relational integrity through PostgreSQL.
- Keep derived statistics out of the core domain model unless there is a demonstrated reason to materialize them.
- Support efficient analytical queries.
- Provide a clean foundation for FastAPI, React, and future AWS deployment.
- Allow the raw source model to evolve independently from the curated domain model.

---

# 2. Physical Database Architecture

The PostgreSQL database uses four logical schemas:

```text
baseball_intelligence
├── reference
├── raw
├── curated
└── analytics
```

## 2.1 Schema Responsibilities

### `reference`

Contains controlled vocabularies and lookup data used by the curated domain.

Examples:

- Game types
- Pitch types
- Pitch results
- Plate appearance event types
- Handedness

Reference tables prevent uncontrolled variations such as:

```text
HR
home run
homerun
HomeRun
```

from being stored as different values in the curated domain.

---

### `raw`

Contains source-oriented imported data.

The raw layer:

- Preserves source vocabulary.
- Preserves source-specific fields.
- Provides traceability back to ingestion batches.
- Allows source data to be retained even when it does not belong in the curated domain.
- Does not depend on curated-domain foreign keys.
- Can contain fields that are later discarded, transformed, or derived.

The raw layer is intentionally less normalized than the curated layer.

---

### `curated`

Contains the normalized baseball domain model.

The curated layer:

- Uses internal PostgreSQL identifiers.
- Uses controlled reference data.
- Enforces primary keys and foreign keys.
- Enforces important uniqueness and check constraints.
- Represents the business/domain model rather than the source file structure.

This is the primary application and analytical domain.

---

### `analytics`

Contains derived analytical objects.

Initial analytics implementation will favor:

- Views
- Materialized views when justified
- Query-based calculations

Derived values should not automatically become stored domain columns.

A statistic should generally be calculated from authoritative underlying data unless there is a demonstrated performance or business reason to materialize it.

---

# 3. Schema Authority and Migration Strategy

PostgreSQL is the authoritative physical schema.

Alembic is the authoritative migration history.

SQLAlchemy models the database for application access but does not independently define the physical database schema.

The relationship is:

```text
PostgreSQL
    ↑
    │ authoritative physical schema
    │
Alembic
    ↑
    │ migration history
    │
SQLAlchemy
    ↑
    │ application data access
    │
FastAPI
```

## 3.1 Responsibilities

### PostgreSQL owns

- Tables
- Columns
- Data types
- Primary keys
- Foreign keys
- Unique constraints
- Check constraints
- Indexes
- Relationships

### Alembic owns

- Migration history
- Intentional schema changes
- Deployment sequencing
- Roll-forward schema changes

### SQLAlchemy owns

- Application-side representation of tables
- Query construction
- Persistence/access from FastAPI
- ORM relationships where useful

---

## 3.2 Schema Change Rule

A physical schema change should follow:

```text
Design decision
        ↓
Review
        ↓
Alembic migration
        ↓
PostgreSQL
        ↓
SQLAlchemy model update
        ↓
Application update
```

SQLAlchemy autogenerate should not be treated as the ultimate authority for physical schema design.

Schema changes should be deliberate and reviewed.

Already-applied migrations should not be edited in persistent/shared environments.

Instead:

```text
Existing migration
        ↓
New requirement
        ↓
New migration
```

---

# 4. Naming Conventions

All database objects use lowercase `snake_case`.

Examples:

```text
plate_appearance
game_player
pitch_type_id
created_at
```

Tables use singular nouns.

Examples:

```text
player
team
game
stadium
pitch
```

Relationship tables use descriptive names.

Examples:

```text
game_team
game_player
```

Primary keys follow:

```text
<table>_id
```

Examples:

```text
player_id
game_id
stadium_id
pitch_id
```

Foreign keys use the referenced primary key name.

Examples:

```text
player_id
team_id
game_id
```

---

# 5. Constraint Naming

Constraints use explicit names.

Examples:

```text
pk_player
fk_game_season
uq_player_mlbam_id
ck_pitch_pitch_number_positive
```

Recommended patterns:

```text
pk_<table>
fk_<table>_<referenced_table>
uq_<table>_<columns>
ck_<table>_<description>
```

Indexes use:

```text
idx_<table>_<columns>
```

Example:

```text
idx_pitch_plate_appearance_id
```

Explicit names make migrations, troubleshooting, and database administration easier.

---

# 6. ID Strategy

## 6.1 Curated Primary Keys

Curated domain tables use:

```sql
BIGINT GENERATED ALWAYS AS IDENTITY
```

Example:

```sql
player_id BIGINT GENERATED ALWAYS AS IDENTITY
```

The internal database identifier is separate from the external MLB identifier.

---

## 6.2 Reference Primary Keys

Reference tables use:

```sql
SMALLINT GENERATED ALWAYS AS IDENTITY
```

Reference datasets are small, making `SMALLINT` appropriate.

---

## 6.3 External IDs

External source identifiers are stored separately.

Examples:

```text
mlbam_id
mlbam_venue_id
game_pk
```

External identifiers should not automatically become internal primary keys.

This separates:

```text
external source identity
```

from:

```text
internal database identity
```

---

# 7. Data Type Strategy

Data types should represent the semantic meaning of a field rather than simply matching the source file type.

## 7.1 Dates

Use:

```sql
DATE
```

when only the calendar date matters.

Examples:

```text
birth_date
game_date
opened_date
```

---

## 7.2 Timestamps

Use:

```sql
TIMESTAMPTZ
```

for actual moments in time.

Examples:

```text
scheduled_start_at
actual_start_at
actual_end_at
created_at
```

---

## 7.3 Physical Measurements

Use:

```sql
DOUBLE PRECISION
```

for most baseball physical measurements.

Examples:

```text
release_speed
launch_angle
plate_x
plate_z
latitude
longitude
```

`REAL` may be used selectively if precision requirements justify it.

---

## 7.4 Exact Decimal Values

Use:

```sql
NUMERIC(p,s)
```

only when exact decimal precision is required.

Do not use NUMERIC by default for all measurements.

---

## 7.5 Text

Use:

```sql
TEXT
```

unless a specific bounded length has a meaningful domain reason.

---

## 7.6 JSONB

Use:

```sql
JSONB
```

for:

- Source payload preservation
- Semi-structured source data
- Data whose structure is not stable enough for curated columns

JSONB should not replace relational modeling where the data represents a core domain concept.

---

# 8. Raw Schema

The raw schema contains source-oriented data.

Current raw tables:

```text
raw
├── ingestion_batch
├── game_metadata
├── player_metadata
├── team_metadata
└── statcast_pitch
```

---

# 9. raw.ingestion_batch

## Grain

One row per ingestion attempt or requested source range.

## Purpose

Tracks ingestion activity and provides operational traceability.

## Structure

```sql
CREATE TABLE raw.ingestion_batch (
    ingestion_batch_id BIGINT GENERATED ALWAYS AS IDENTITY,
    source_name TEXT NOT NULL,
    source_file_name TEXT,
    source_date_from DATE,
    source_date_to DATE,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    records_read INTEGER,
    records_inserted INTEGER,
    records_skipped INTEGER,
    records_failed INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT pk_ingestion_batch PRIMARY KEY (ingestion_batch_id),

    CONSTRAINT ck_ingestion_batch_status
        CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),

    CONSTRAINT ck_ingestion_batch_source_dates
        CHECK (
            source_date_from IS NULL
            OR source_date_to IS NULL
            OR source_date_from <= source_date_to
        ),

    CONSTRAINT ck_ingestion_batch_records_read
        CHECK (records_read IS NULL OR records_read >= 0),

    CONSTRAINT ck_ingestion_batch_records_inserted
        CHECK (records_inserted IS NULL OR records_inserted >= 0),

    CONSTRAINT ck_ingestion_batch_records_skipped
        CHECK (records_skipped IS NULL OR records_skipped >= 0),

    CONSTRAINT ck_ingestion_batch_records_failed
        CHECK (records_failed IS NULL OR records_failed >= 0)
);
```

---

# 10. raw.game_metadata

## Grain

One game from one source.

## Structure

```sql
CREATE TABLE raw.game_metadata (
    raw_game_metadata_id BIGINT GENERATED ALWAYS AS IDENTITY,
    ingestion_batch_id BIGINT NOT NULL,
    source_name TEXT NOT NULL,
    game_pk BIGINT NOT NULL,
    game_date DATE NOT NULL,
    game_type TEXT,
    home_team_id BIGINT,
    home_team_abbreviation TEXT,
    away_team_id BIGINT,
    away_team_abbreviation TEXT,
    venue_id BIGINT,
    venue_name TEXT,
    scheduled_start_at TIMESTAMPTZ,
    actual_start_at TIMESTAMPTZ,
    actual_end_at TIMESTAMPTZ,
    game_status TEXT,
    source_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_game_metadata PRIMARY KEY (raw_game_metadata_id),

    CONSTRAINT fk_game_metadata_ingestion_batch
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batch (ingestion_batch_id),

    CONSTRAINT uq_game_metadata_source_game
        UNIQUE (source_name, game_pk)
);
```

---

# 11. raw.player_metadata

## Grain

One player from one source.

## Structure

```sql
CREATE TABLE raw.player_metadata (
    raw_player_metadata_id BIGINT GENERATED ALWAYS AS IDENTITY,
    ingestion_batch_id BIGINT NOT NULL,
    source_name TEXT NOT NULL,
    mlbam_id BIGINT NOT NULL,
    full_name TEXT,
    first_name TEXT,
    last_name TEXT,
    birth_date DATE,
    birth_city TEXT,
    birth_country TEXT,
    height TEXT,
    weight INTEGER,
    primary_position_code TEXT,
    primary_position_name TEXT,
    primary_position_abbreviation TEXT,
    bat_side TEXT,
    pitch_hand TEXT,
    primary_number TEXT,
    mlb_debut_date DATE,
    active BOOLEAN,
    source_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT pk_player_metadata PRIMARY KEY (raw_player_metadata_id),

    CONSTRAINT fk_player_metadata_ingestion_batch
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batch (ingestion_batch_id),

    CONSTRAINT uq_player_metadata_source_mlbam
        UNIQUE (source_name, mlbam_id)
);
```

---

# 12. raw.team_metadata

## Grain

One team from one source.

## Structure

```sql
CREATE TABLE raw.team_metadata (
    raw_team_metadata_id BIGINT GENERATED ALWAYS AS IDENTITY,
    ingestion_batch_id BIGINT NOT NULL,
    source_name TEXT NOT NULL,
    mlbam_id BIGINT NOT NULL,
    name TEXT,
    team_name TEXT,
    short_name TEXT,
    abbreviation TEXT,
    location_name TEXT,
    league_id BIGINT,
    league_name TEXT,
    division_id BIGINT,
    division_name TEXT,
    venue_id BIGINT,
    venue_name TEXT,
    first_year_of_play SMALLINT,
    active BOOLEAN,
    source_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT pk_team_metadata PRIMARY KEY (raw_team_metadata_id),

    CONSTRAINT fk_team_metadata_ingestion_batch
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batch (ingestion_batch_id),

    CONSTRAINT uq_team_metadata_source_mlbam
        UNIQUE (source_name, mlbam_id)
);
```

---

# 13. raw.statcast_pitch

## Grain

One Statcast pitch.

The raw Statcast layer preserves the source-oriented pitch record.

The source identity is:

```text
game_pk + at_bat_number + pitch_number
```

`sv_id` is not used as the source identity because Baseball Savant documentation identifies it as a non-unique play-event identifier within a game.

## Primary Key

```text
raw_statcast_pitch_id
```

## Source Identity

```text
UNIQUE(game_pk, at_bat_number, pitch_number)
```

## Important Raw Fields

The raw table preserves the complete relevant Statcast dataset, including source-specific fields that are not part of the curated domain.

The final implementation includes:

```text
raw_statcast_pitch_id
ingestion_batch_id
game_pk
at_bat_number
pitch_number
game_date
game_year
game_type
player_name
batter
pitcher
home_team
away_team
fielder_2
fielder_3
fielder_4
fielder_5
fielder_6
fielder_7
fielder_8
fielder_9
pitch_type
pitch_name
events
description
type
des
zone
balls
strikes
outs_when_up
inning
inning_topbot
stand
p_throws
hit_location
bb_type
on_1b
on_2b
on_3b
release_speed
release_pos_x
release_pos_y
release_pos_z
pfx_x
pfx_z
vx0
vy0
vz0
ax
ay
az
effective_speed
release_spin
release_extension
spin_axis
api_break_z_with_gravity
api_break_x_arm
api_break_x_batter_in
plate_x
plate_z
sz_top
sz_bot
hc_x
hc_y
hit_distance
launch_speed
launch_angle
hyper_speed
launch_speed_angle
home_score
away_score
bat_score
fld_score
post_home_score
post_away_score
post_bat_score
post_fld_score
home_score_diff
bat_score_diff
home_win_exp
bat_win_exp
delta_home_win_exp
delta_run_exp
estimated_ba_using_speedangle
estimated_woba_using_speedangle
woba_value
woba_denom
babip_value
iso_value
if_fielding_alignment
of_fielding_alignment
age_pit
age_bat
n_thruorder_pitcher
n_priorpa_thisgame_player_at_bat
pitcher_days_since_prev_game
batter_days_since_prev_game
pitcher_days_until_next_game
batter_days_until_next_game
arm_angle
attack_angle
attack_direction
swing_path_tilt
intercept_ball_minus_batter_pos_x_inches
intercept_ball_minus_batter_pos_y_inches
source_payload
created_at
```

The exact physical data types should follow the data-type strategy in this document.

Important checks:

```sql
CHECK (at_bat_number > 0)
CHECK (pitch_number > 0)
```

Important indexes:

```sql
CREATE INDEX idx_statcast_pitch_ingestion_batch_id
    ON raw.statcast_pitch (ingestion_batch_id);

CREATE INDEX idx_statcast_pitch_game_pk
    ON raw.statcast_pitch (game_pk);

CREATE INDEX idx_statcast_pitch_pitcher
    ON raw.statcast_pitch (pitcher);

CREATE INDEX idx_statcast_pitch_batter
    ON raw.statcast_pitch (batter);
```

---

# 14. Reference Schema

The V1 reference schema contains five tables:

```text
reference
├── game_type
├── pitch_type
├── pitch_result
├── event_type
└── hand
```

Reference data is loaded before curated domain data.

Reference values should be authoritative and controlled.

---

# 15. reference.game_type

## Grain

One row per controlled game type.

## Structure

```sql
CREATE TABLE reference.game_type (
    game_type_id SMALLINT GENERATED ALWAYS AS IDENTITY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    CONSTRAINT pk_game_type PRIMARY KEY (game_type_id),
    CONSTRAINT uq_game_type_code UNIQUE (code),
    CONSTRAINT uq_game_type_name UNIQUE (name)
);
```

Potential values include:

```text
E  Exhibition
S  Spring Training
R  Regular Season
F  Wild Card
D  Division Series
L  League Championship Series
W  World Series
```

These values should be seeded from an authoritative source rather than assumed to be exhaustive.

---

# 16. reference.pitch_type

## Grain

One row per controlled pitch type.

## Structure

```sql
CREATE TABLE reference.pitch_type (
    pitch_type_id SMALLINT GENERATED ALWAYS AS IDENTITY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    CONSTRAINT pk_pitch_type PRIMARY KEY (pitch_type_id),
    CONSTRAINT uq_pitch_type_code UNIQUE (code),
    CONSTRAINT uq_pitch_type_name UNIQUE (name)
);
```

Source pitch-type codes should be mapped into this controlled vocabulary during curation.

---

# 17. reference.pitch_result

## Grain

One row per controlled pitch-level result.

## Structure

```sql
CREATE TABLE reference.pitch_result (
    pitch_result_id SMALLINT GENERATED ALWAYS AS IDENTITY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    CONSTRAINT pk_pitch_result PRIMARY KEY (pitch_result_id),
    CONSTRAINT uq_pitch_result_code UNIQUE (code),
    CONSTRAINT uq_pitch_result_name UNIQUE (name)
);
```

Examples:

```text
called_strike
swinging_strike
ball
foul
hit_into_play
blocked_ball
```

This table represents the result of an individual pitch.

It is intentionally separate from `event_type`, which represents the final statistical result of a plate appearance.

---

# 18. reference.event_type

## Grain

One row per controlled plate appearance outcome.

## Structure

```sql
CREATE TABLE reference.event_type (
    event_type_id SMALLINT GENERATED ALWAYS AS IDENTITY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,

    CONSTRAINT pk_event_type PRIMARY KEY (event_type_id),
    CONSTRAINT uq_event_type_code UNIQUE (code),
    CONSTRAINT uq_event_type_name UNIQUE (name)
);
```

Examples:

```text
single
double
triple
home_run
walk
intentional_walk
strikeout
field_out
grounded_into_double_play
```

The final V1 seed list will be determined from the authoritative source vocabulary.

---

# 19. reference.hand

## Grain

One row per controlled handedness value.

## Structure

```sql
CREATE TABLE reference.hand (
    hand_id SMALLINT GENERATED ALWAYS AS IDENTITY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,

    CONSTRAINT pk_hand PRIMARY KEY (hand_id),
    CONSTRAINT uq_hand_code UNIQUE (code),
    CONSTRAINT uq_hand_name UNIQUE (name)
);
```

Expected values:

```text
L  Left
R  Right
S  Switch
```

`S` applies to batting handedness.

Pitchers generally use `L` or `R` for throwing hand.

---

# 20. Curated Schema

The curated V1 domain consists of:

```text
curated
├── season
├── team
├── player
├── stadium
├── game
├── game_team
├── game_player
├── plate_appearance
└── pitch
```

The design follows the principle:

> Store each authoritative data point at the lowest appropriate grain without unnecessarily duplicating it across higher-level entities.

---

# 21. curated.season

## Grain

One row per baseball season.

## Structure

```sql
CREATE TABLE curated.season (
    season_id BIGINT GENERATED ALWAYS AS IDENTITY,
    season_year SMALLINT NOT NULL,
    all_star_game_date DATE,
    trade_deadline_date DATE,
    postseason_start_date DATE,
    world_series_start_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_season PRIMARY KEY (season_id),
    CONSTRAINT uq_season_season_year UNIQUE (season_year),
    CONSTRAINT ck_season_season_year CHECK (season_year >= 1900)
);
```

The `season` entity provides a stable place for season-level calendar information.

Examples:

- All-Star Game date
- Trade deadline
- Postseason start
- World Series start

Season statistics do not belong in this table.

`opening_day_date` is intentionally not stored in V1 because the definition can be ambiguous in the context of individual teams and the MLB season.

---

# 22. curated.team

## Grain

One row per team/organization.

## Structure

```sql
CREATE TABLE curated.team (
    team_id BIGINT GENERATED ALWAYS AS IDENTITY,
    mlbam_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    abbreviation TEXT,
    location_name TEXT,
    first_year_of_play SMALLINT,
    active BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_team PRIMARY KEY (team_id),
    CONSTRAINT uq_team_mlbam_id UNIQUE (mlbam_id)
);
```

The team entity represents the stable organization.

It does not store:

- Current league
- Current division
- Current stadium
- Season statistics
- Game-specific statistics

Temporal team/league/division relationships can be modeled later if required.

---

# 23. curated.player

## Grain

One row per stable/canonical player.

## Structure

```sql
CREATE TABLE curated.player (
    player_id BIGINT GENERATED ALWAYS AS IDENTITY,
    mlbam_id BIGINT NOT NULL,
    full_name TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    birth_date DATE,
    birth_country TEXT,
    height_inches SMALLINT,
    weight_pounds SMALLINT,
    bat_hand_id SMALLINT,
    throw_hand_id SMALLINT,
    mlb_debut_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_player PRIMARY KEY (player_id),
    CONSTRAINT uq_player_mlbam_id UNIQUE (mlbam_id),

    CONSTRAINT fk_player_bat_hand
        FOREIGN KEY (bat_hand_id)
        REFERENCES reference.hand(hand_id),

    CONSTRAINT fk_player_throw_hand
        FOREIGN KEY (throw_hand_id)
        REFERENCES reference.hand(hand_id),

    CONSTRAINT ck_player_height_inches
        CHECK (
            height_inches IS NULL
            OR height_inches BETWEEN 36 AND 96
        ),

    CONSTRAINT ck_player_weight_pounds
        CHECK (
            weight_pounds IS NULL
            OR weight_pounds BETWEEN 50 AND 500
        )
);
```

The player table does not store:

- Current team
- Current age
- Primary position
- Game statistics
- Season statistics

Age is derived from:

```text
player.birth_date
+
game.game_date
```

The player's current team is intentionally not stored because team membership is temporal.

---

# 24. curated.stadium

## Grain

One row per physical baseball venue.

## Structure

```sql
CREATE TABLE curated.stadium (
    stadium_id BIGINT GENERATED ALWAYS AS IDENTITY,
    mlbam_venue_id BIGINT,
    name TEXT NOT NULL,
    city TEXT,
    state_province TEXT,
    country TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    capacity INTEGER,
    roof_type TEXT,
    left_field_distance_ft DOUBLE PRECISION,
    left_center_field_distance_ft DOUBLE PRECISION,
    center_field_distance_ft DOUBLE PRECISION,
    right_center_field_distance_ft DOUBLE PRECISION,
    right_field_distance_ft DOUBLE PRECISION,
    active BOOLEAN,
    opened_date DATE,
    closed_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_stadium PRIMARY KEY (stadium_id),

    CONSTRAINT uq_stadium_mlbam_venue_id
        UNIQUE (mlbam_venue_id),

    CONSTRAINT ck_stadium_latitude
        CHECK (
            latitude IS NULL
            OR latitude BETWEEN -90 AND 90
        ),

    CONSTRAINT ck_stadium_longitude
        CHECK (
            longitude IS NULL
            OR longitude BETWEEN -180 AND 180
        ),

    CONSTRAINT ck_stadium_capacity
        CHECK (
            capacity IS NULL
            OR capacity > 0
        ),

    CONSTRAINT ck_stadium_left_field_distance
        CHECK (
            left_field_distance_ft IS NULL
            OR left_field_distance_ft > 0
        ),

    CONSTRAINT ck_stadium_left_center_field_distance
        CHECK (
            left_center_field_distance_ft IS NULL
            OR left_center_field_distance_ft > 0
        ),

    CONSTRAINT ck_stadium_center_field_distance
        CHECK (
            center_field_distance_ft IS NULL
            OR center_field_distance_ft > 0
        ),

    CONSTRAINT ck_stadium_right_center_field_distance
        CHECK (
            right_center_field_distance_ft IS NULL
            OR right_center_field_distance_ft > 0
        ),

    CONSTRAINT ck_stadium_right_field_distance
        CHECK (
            right_field_distance_ft IS NULL
            OR right_field_distance_ft > 0
        )
);
```

Stadium dimensions are standardized to feet.

The dimensions are stored directly on the stadium because the project needs analytical queries such as:

```text
Which stadium has the longest left field?
Which stadium has the shortest center field?
```

V1 does not model historical wall configurations.

If historical dimensions become an analytical requirement, a temporal stadium-dimension model can be introduced later.

The stadium does not store a home team.

A team can move stadiums, and a stadium can potentially have different occupants over time.

---

# 25. curated.game

## Grain

One row per baseball game.

## Structure

```sql
CREATE TABLE curated.game (
    game_id BIGINT GENERATED ALWAYS AS IDENTITY,
    game_pk BIGINT NOT NULL,
    season_id BIGINT NOT NULL,
    game_type_id SMALLINT NOT NULL,
    stadium_id BIGINT,
    game_date DATE NOT NULL,
    scheduled_start_at TIMESTAMPTZ,
    actual_start_at TIMESTAMPTZ,
    actual_end_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    attendance INTEGER,
    temperature_f DOUBLE PRECISION,
    wind_speed_mph DOUBLE PRECISION,
    wind_direction_degrees DOUBLE PRECISION,
    weather_condition TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_game PRIMARY KEY (game_id),

    CONSTRAINT uq_game_game_pk
        UNIQUE (game_pk),

    CONSTRAINT fk_game_season
        FOREIGN KEY (season_id)
        REFERENCES curated.season(season_id),

    CONSTRAINT fk_game_game_type
        FOREIGN KEY (game_type_id)
        REFERENCES reference.game_type(game_type_id),

    CONSTRAINT fk_game_stadium
        FOREIGN KEY (stadium_id)
        REFERENCES curated.stadium(stadium_id),

    CONSTRAINT ck_game_status
        CHECK (
            status IN (
                'SCHEDULED',
                'IN_PROGRESS',
                'FINAL',
                'POSTPONED',
                'SUSPENDED',
                'CANCELLED'
            )
        ),

    CONSTRAINT ck_game_attendance
        CHECK (
            attendance IS NULL
            OR attendance >= 0
        ),

    CONSTRAINT ck_game_wind_direction_degrees
        CHECK (
            wind_direction_degrees IS NULL
            OR (
                wind_direction_degrees >= 0
                AND wind_direction_degrees < 360
            )
        )
);
```

Indexes:

```sql
CREATE INDEX idx_game_game_date
    ON curated.game (game_date);

CREATE INDEX idx_game_season_id
    ON curated.game (season_id);
```

Game duration is intentionally not stored.

It is derived from:

```text
actual_end_at - actual_start_at
```

No hard database constraint requires:

```text
actual_end_at >= actual_start_at
```

because source data may contain anomalies or corrections.

Home and away teams are not stored directly on `game`.

They are represented through `game_team`.

---

# 26. curated.game_team

## Grain

One row per team per game.

A normal MLB game contains:

```text
1 HOME
1 AWAY
```

## Structure

```sql
CREATE TABLE curated.game_team (
    game_team_id BIGINT GENERATED ALWAYS AS IDENTITY,
    game_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    home_away TEXT NOT NULL,
    runs INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_game_team PRIMARY KEY (game_team_id),

    CONSTRAINT uq_game_team_game_team
        UNIQUE (game_id, team_id),

    CONSTRAINT uq_game_team_game_home_away
        UNIQUE (game_id, home_away),

    CONSTRAINT fk_game_team_game
        FOREIGN KEY (game_id)
        REFERENCES curated.game(game_id),

    CONSTRAINT fk_game_team_team
        FOREIGN KEY (team_id)
        REFERENCES curated.team(team_id),

    CONSTRAINT ck_game_team_home_away
        CHECK (home_away IN ('HOME', 'AWAY')),

    CONSTRAINT ck_game_team_runs
        CHECK (
            runs IS NULL
            OR runs >= 0
        )
);
```

Index:

```sql
CREATE INDEX idx_game_team_team_id
    ON curated.game_team (team_id);
```

`runs` is retained because it represents the team's result in a particular game.

The following are intentionally not stored in V1:

- Win/loss
- Hits
- Home runs
- Errors
- Team batting statistics
- Team pitching statistics

Those values can be derived from authoritative game events.

The unique constraint:

```text
(game_id, home_away)
```

prevents multiple HOME rows or multiple AWAY rows for the same game.

The database does not enforce that a normal game has exactly two `game_team` rows.

That business rule is enforced during ingestion/curation.

---

# 27. curated.game_player

## Grain

One row per player who actually participated in a game for a team.

A player who was on the bench but did not participate does not receive a row.

## Structure

```sql
CREATE TABLE curated.game_player (
    game_player_id BIGINT GENERATED ALWAYS AS IDENTITY,
    game_team_id BIGINT NOT NULL,
    player_id BIGINT NOT NULL,
    starter BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_game_player PRIMARY KEY (game_player_id),

    CONSTRAINT uq_game_player_game_team_player
        UNIQUE (game_team_id, player_id),

    CONSTRAINT fk_game_player_game_team
        FOREIGN KEY (game_team_id)
        REFERENCES curated.game_team(game_team_id),

    CONSTRAINT fk_game_player_player
        FOREIGN KEY (player_id)
        REFERENCES curated.player(player_id)
);
```

Index:

```sql
CREATE INDEX idx_game_player_player_id
    ON curated.game_player (player_id);
```

A player's game participation is represented by `game_player`.

The model intentionally does not currently store:

- Batting order
- Detailed fielding positions
- Pitcher entry time
- Pitcher exit time
- Pitcher usage type
- Game statistics

Those can be added through future domain extensions when justified.

A player can occupy multiple positions in a game, which is why a single `position_type_id` is not stored on `game_player`.

---

# 28. curated.plate_appearance

## Grain

One row per completed plate appearance involving one batter and one pitcher in one game.

## Structure

```sql
CREATE TABLE curated.plate_appearance (
    plate_appearance_id BIGINT GENERATED ALWAYS AS IDENTITY,
    game_id BIGINT NOT NULL,
    at_bat_number INTEGER NOT NULL,
    batter_game_player_id BIGINT NOT NULL,
    pitcher_game_player_id BIGINT NOT NULL,
    event_type_id SMALLINT NOT NULL,
    bat_hand_id SMALLINT,
    inning SMALLINT NOT NULL,
    inning_topbot TEXT NOT NULL,
    outs_at_beginning SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_plate_appearance PRIMARY KEY (plate_appearance_id),

    CONSTRAINT uq_plate_appearance_game_at_bat
        UNIQUE (game_id, at_bat_number),

    CONSTRAINT fk_plate_appearance_game
        FOREIGN KEY (game_id)
        REFERENCES curated.game(game_id),

    CONSTRAINT fk_plate_appearance_batter
        FOREIGN KEY (batter_game_player_id)
        REFERENCES curated.game_player(game_player_id),

    CONSTRAINT fk_plate_appearance_pitcher
        FOREIGN KEY (pitcher_game_player_id)
        REFERENCES curated.game_player(game_player_id),

    CONSTRAINT fk_plate_appearance_event_type
        FOREIGN KEY (event_type_id)
        REFERENCES reference.event_type(event_type_id),

    CONSTRAINT fk_plate_appearance_bat_hand
        FOREIGN KEY (bat_hand_id)
        REFERENCES reference.hand(hand_id),

    CONSTRAINT ck_plate_appearance_at_bat_number
        CHECK (at_bat_number > 0),

    CONSTRAINT ck_plate_appearance_inning
        CHECK (inning > 0),

    CONSTRAINT ck_plate_appearance_inning_topbot
        CHECK (inning_topbot IN ('TOP', 'BOT')),

    CONSTRAINT ck_plate_appearance_outs_at_beginning
        CHECK (outs_at_beginning BETWEEN 0 AND 2)
);
```

Indexes:

```sql
CREATE INDEX idx_plate_appearance_batter_game_player_id
    ON curated.plate_appearance (batter_game_player_id);

CREATE INDEX idx_plate_appearance_pitcher_game_player_id
    ON curated.plate_appearance (pitcher_game_player_id);
```

A PA references `game_player` rather than `player`.

This allows the database to represent:

```text
Game
  ↓
GameTeam
  ↓
GamePlayer
  ↓
PlateAppearance
```

The foreign key proves that the batter and pitcher are known game participants.

The basic foreign keys do not prove that both game players belong to the same game as the PA.

That cross-entity business rule is enforced during ingestion/curation.

`game_id` is intentionally retained on `plate_appearance` even though it is indirectly reachable through `game_player`.

It provides the natural PA-to-game relationship and supports the unique source bridge:

```text
(game_id, at_bat_number)
```

`at_bat_number` is the source bridge and is unique within a game.

`bat_hand_id` is nullable because the system must not manufacture a batting hand when the source does not provide a reliable value.

`outs_at_beginning` preserves the authoritative Statcast source value.

The system does not recalculate this value in V1.

---

# 29. curated.pitch

## Grain

One row per pitch thrown during one plate appearance.

The hierarchy is:

```text
Game
  ↓
PlateAppearance
  ↓
Pitch
```

A pitch references only its plate appearance for the baseball hierarchy.

The pitch does not duplicate:

- Game ID
- Batter ID
- Pitcher ID
- Team ID
- Inning
- Inning half
- PA event type

Those values are reachable through relationships.

## Structure

```sql
CREATE TABLE curated.pitch (
    pitch_id BIGINT GENERATED ALWAYS AS IDENTITY,

    plate_appearance_id BIGINT NOT NULL,
    pitch_number INTEGER NOT NULL,

    pitch_type_id SMALLINT,
    pitch_result_id SMALLINT,

    balls SMALLINT,
    strikes SMALLINT,
    zone SMALLINT,

    plate_x DOUBLE PRECISION,
    plate_z DOUBLE PRECISION,
    sz_top DOUBLE PRECISION,
    sz_bot DOUBLE PRECISION,

    release_speed DOUBLE PRECISION,
    effective_speed DOUBLE PRECISION,
    release_spin DOUBLE PRECISION,
    spin_axis DOUBLE PRECISION,

    release_pos_x DOUBLE PRECISION,
    release_pos_y DOUBLE PRECISION,
    release_pos_z DOUBLE PRECISION,
    release_extension DOUBLE PRECISION,

    pfx_x DOUBLE PRECISION,
    pfx_z DOUBLE PRECISION,

    vx0 DOUBLE PRECISION,
    vy0 DOUBLE PRECISION,
    vz0 DOUBLE PRECISION,

    ax DOUBLE PRECISION,
    ay DOUBLE PRECISION,
    az DOUBLE PRECISION,

    home_score SMALLINT,
    away_score SMALLINT,
    post_home_score SMALLINT,
    post_away_score SMALLINT,

    home_win_exp DOUBLE PRECISION,
    bat_win_exp DOUBLE PRECISION,
    delta_home_win_exp DOUBLE PRECISION,
    delta_run_exp DOUBLE PRECISION,

    estimated_ba_using_speedangle DOUBLE PRECISION,
    estimated_woba_using_speedangle DOUBLE PRECISION,
    woba_value DOUBLE PRECISION,

    hc_x DOUBLE PRECISION,
    hc_y DOUBLE PRECISION,
    hit_distance DOUBLE PRECISION,
    launch_speed DOUBLE PRECISION,
    launch_angle DOUBLE PRECISION,
    hyper_speed DOUBLE PRECISION,

    arm_angle DOUBLE PRECISION,
    attack_angle DOUBLE PRECISION,
    attack_direction DOUBLE PRECISION,
    swing_path_tilt DOUBLE PRECISION,
    intercept_ball_minus_batter_pos_x_inches DOUBLE PRECISION,
    intercept_ball_minus_batter_pos_y_inches DOUBLE PRECISION,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_pitch PRIMARY KEY (pitch_id),

    CONSTRAINT uq_pitch_plate_appearance_pitch_number
        UNIQUE (plate_appearance_id, pitch_number),

    CONSTRAINT fk_pitch_plate_appearance
        FOREIGN KEY (plate_appearance_id)
        REFERENCES curated.plate_appearance (plate_appearance_id),

    CONSTRAINT fk_pitch_pitch_type
        FOREIGN KEY (pitch_type_id)
        REFERENCES reference.pitch_type (pitch_type_id),

    CONSTRAINT fk_pitch_pitch_result
        FOREIGN KEY (pitch_result_id)
        REFERENCES reference.pitch_result (pitch_result_id),

    CONSTRAINT ck_pitch_pitch_number_positive
        CHECK (pitch_number > 0),

    CONSTRAINT ck_pitch_balls
        CHECK (
            balls IS NULL
            OR balls BETWEEN 0 AND 3
        ),

    CONSTRAINT ck_pitch_strikes
        CHECK (
            strikes IS NULL
            OR strikes BETWEEN 0 AND 2
        ),

    CONSTRAINT ck_pitch_zone
        CHECK (
            zone IS NULL
            OR zone BETWEEN 1 AND 14
        )
);
```

Indexes:

```sql
CREATE INDEX idx_pitch_plate_appearance_id
    ON curated.pitch (plate_appearance_id);

CREATE INDEX idx_pitch_pitch_type_id
    ON curated.pitch (pitch_type_id);

CREATE INDEX idx_pitch_pitch_result_id
    ON curated.pitch (pitch_result_id);
```

The unique constraint:

```text
(plate_appearance_id, pitch_number)
```

ensures that pitch numbers are unique within a PA.

---

# 30. Pitch Counts and Location

The following values are stored directly on `pitch`:

```text
balls
strikes
zone
plate_x
plate_z
sz_top
sz_bot
```

They are nullable because source availability varies.

Constraints:

```text
balls:   0–3
strikes: 0–2
zone:    1–14
```

No arbitrary physical range checks are applied to the Statcast measurement fields.

---

# 31. Statcast Plate Location Methodology

The project preserves the source values rather than mathematically normalizing historical data.

Important source methodology differences exist across seasons.

For example:

- `plate_x` and `plate_z` methodology changed beginning in 2026 to align with Automated Ball-Strike System measurements.
- `sz_top` and `sz_bot` methodology also changed beginning in 2026.

Therefore the project stores one set of columns:

```text
plate_x
plate_z
sz_top
sz_bot
```

while preserving the original source values.

Historical methodology differences should be documented in analytical queries and documentation rather than silently altering source values.

---

# 32. Pitch Physics

The following pitch-level physical measurements are stored as nullable `DOUBLE PRECISION`:

```text
release_speed
effective_speed
release_spin
spin_axis
release_pos_x
release_pos_y
release_pos_z
release_extension
pfx_x
pfx_z
vx0
vy0
vz0
ax
ay
az
```

No arbitrary physical-range checks are applied in V1.

The source is treated as authoritative.

Data-quality validation can be added later after examining actual source distributions.

---

# 33. Pitch Game-State Measurements

The following fields are retained in curated:

```text
home_score
away_score
post_home_score
post_away_score
home_win_exp
bat_win_exp
delta_home_win_exp
delta_run_exp
```

These represent pitch-time game state or source analytical measurements.

The following remain raw-only in V1:

```text
bat_score
fld_score
post_bat_score
post_fld_score
home_score_diff
bat_score_diff
```

The raw fields are preserved for traceability.

They can be derived from canonical game context when needed.

---

# 34. Expected and Analytical Metrics

The following remain in curated:

```text
estimated_ba_using_speedangle
estimated_woba_using_speedangle
woba_value
```

The following remain raw-only:

```text
woba_denom
babip_value
iso_value
```

The design principle is:

> Complex source-derived analytical measurements that cannot reasonably be reproduced from the domain model should be preserved.

Simple statistical components that can be derived from authoritative domain data should generally be calculated in analytics.

---

# 35. Batted-Ball Coordinates

The following fields remain directly on `pitch`:

```text
hc_x
hc_y
```

No separate `batted_ball` entity is created in V1.

This is intentional because:

- The measurements are pitch-level source attributes.
- Not every pitch produces a batted ball.
- A separate entity would add complexity without providing enough current value.

Future modeling can introduce a dedicated batted-ball/event model if the analytical requirements justify it.

---

# 36. Batted-Ball Measurements

The following remain on `pitch`:

```text
hit_distance
launch_speed
launch_angle
hyper_speed
```

`launch_speed_angle` remains raw-only in V1.

Analytics may derive classifications from:

```text
launch_speed
+
launch_angle
```

but the project should not assume that a derived classification exactly matches the source's methodology without validating the definitions.

---

# 37. Bat-Tracking Data

The following fields remain on `pitch`:

```text
arm_angle
attack_angle
attack_direction
swing_path_tilt
intercept_ball_minus_batter_pos_x_inches
intercept_ball_minus_batter_pos_y_inches
```

No separate `swing` or `bat_tracking` entity is created in V1.

Historical missing values remain NULL.

The data model should not manufacture values for seasons where the source did not provide them.

---

# 38. Raw-Only Statcast Fields

The following remain in raw rather than curated:

```text
type
des
player_name
fielder_2
fielder_3
fielder_4
fielder_5
fielder_6
fielder_7
fielder_8
fielder_9
outs_when_up
inning
inning_topbot
stand
p_throws
n_thruorder_pitcher
n_priorpa_thisgame_player_at_bat
pitcher_days_since_prev_game
batter_days_since_prev_game
pitcher_days_until_next_game
batter_days_until_next_game
age_pit
age_bat
umpire
launch_speed_angle
```

Reasons vary by field.

Examples:

- `player_name` is a source representation; canonical player identity is represented by `player`.
- `age_pit` and `age_bat` are derived from birth date and game date.
- `inning` and `inning_topbot` belong naturally to the PA.
- `stand` is represented by `plate_appearance.bat_hand_id`.
- `p_throws` is represented through the player's throwing hand.
- `fielder_*` fields are source-specific defensive representations.
- `n_thruorder_pitcher` and related usage metrics are analytical/derived concepts.

---

# 39. Deprecated Statcast Fields

The following deprecated or source-specific fields remain in the raw layer/source payload rather than curated:

```text
spin_dir
spin_rate_deprecated
break_angle_deprecated
break_length_deprecated
tfs_deprecated
tfs_zulu_deprecated
age_pit_legacy
age_bat_legacy
sv_id
```

These values remain available for source traceability without polluting the curated domain.

---

# 40. Reference Data Mapping

Raw source vocabulary should be mapped into controlled reference vocabulary during curation.

Conceptually:

```text
Raw Source
    ↓
Source value
    ↓
Mapping logic
    ↓
Reference entity
    ↓
Curated FK
```

Examples:

```text
raw.pitch_type
      ↓
reference.pitch_type
      ↓
curated.pitch.pitch_type_id
```

```text
raw.events
      ↓
reference.event_type
      ↓
curated.plate_appearance.event_type_id
```

```text
raw.description/type
      ↓
mapping logic
      ↓
reference.pitch_result
      ↓
curated.pitch.pitch_result_id
```

```text
raw.bat_side / source hand
      ↓
reference.hand
      ↓
curated.player.bat_hand_id
```

---

# 41. Raw Versus Curated Philosophy

The raw layer and curated layer intentionally have different purposes.

## Raw

The raw layer asks:

> What did the source give us?

## Curated

The curated layer asks:

> What does the data mean in our baseball domain model?

This allows the project to preserve source information without allowing source-specific structure to dictate the application's domain model.

---

# 42. Derived Data Philosophy

The project follows a strong default:

> Calculate statistics from authoritative underlying data whenever practical.

Examples of values that should generally be derived:

```text
player age
game duration
team win/loss
batting averages
on-base percentage
slugging percentage
OPS
ERA
WHIP
pitch counts
season totals
game totals
```

Materialization can be introduced when there is a demonstrated need for:

- Query performance
- Repeated expensive computation
- Dashboard responsiveness
- Stable analytical datasets

Materialized values should not be introduced simply because a value can be calculated.

---

# 43. Referential Integrity

The curated layer uses standard PostgreSQL foreign keys.

Primary dependency chain:

```text
reference
    ↓
season
team
player
stadium
    ↓
game
    ↓
game_team
    ↓
game_player
    ↓
plate_appearance
    ↓
pitch
```

More specifically:

```text
team
  ↓
game_team
  ↓
game_player
  ↓
plate_appearance
  ↓
pitch
```

And:

```text
season ───────────────→ game
game_type ────────────→ game
stadium ──────────────→ game
```

---

# 44. Business Rules Versus Database Constraints

Not every baseball rule can or should be enforced using a simple relational constraint.

## Database constraints should enforce

Examples:

```text
Primary keys
Foreign keys
Unique identifiers
Unique game/team relationships
Valid HOME/AWAY values
Valid pitch counts
Valid pitch numbers
Valid inning numbers
Valid reference IDs
```

## Ingestion/business logic should enforce

Examples:

```text
A normal game has exactly one HOME team.
A normal game has exactly one AWAY team.
A normal game has two participating teams.
A PA's batter and pitcher belong to the same game.
A player actually participated before receiving a GamePlayer record.
A completed game has the appropriate game participants.
```

Some of these rules could theoretically be enforced with triggers or more complex constraints, but V1 intentionally keeps them in the ingestion/curation layer.

---

# 45. Transaction Strategy

Curated game loads should use database transactions.

The conceptual load is:

```text
BEGIN
    load Season
    load Team
    load Player
    load Stadium
    load Game
    load GameTeam
    load GamePlayer
    load PlateAppearance
    load Pitch
COMMIT
```

If a required portion fails:

```text
ROLLBACK
```

This prevents partially curated games from remaining in the database.

---

# 46. Load Dependency Order

Reference data is loaded first.

Then:

```text
reference
    ↓
season
team
player
stadium
    ↓
game
    ↓
game_team
    ↓
game_player
    ↓
plate_appearance
    ↓
pitch
```

This order follows the foreign-key dependency structure.

No deferrable foreign keys are required for V1.

Normal immediate foreign key enforcement is preferred.

---

# 47. Raw Layer Independence

The raw layer does not depend on the curated domain.

For example:

```text
raw.statcast_pitch
```

does not require:

```text
curated.player
curated.game
curated.team
```

to exist before the source data can be stored.

This is intentional.

The source data should be captured first.

Curation can then resolve:

```text
source identity
        ↓
canonical domain identity
```

---

# 48. Data Lineage

The architecture supports lineage from source through application:

```text
Baseball Savant / MLB Stats API
            ↓
       ingestion_batch
            ↓
           raw
            ↓
        transform
            ↓
         curated
            ↓
        analytics
            ↓
          FastAPI
            ↓
          React
```

The `ingestion_batch_id` provides an operational connection between raw records and the ingestion process that produced them.

---

# 49. Application Architecture Relationship

The database is not directly exposed to the React application.

The intended application flow is:

```text
React
  ↓
FastAPI
  ↓
SQLAlchemy
  ↓
PostgreSQL
```

External baseball sources are not called directly by React.

Instead:

```text
External Sources
       ↓
Python Ingestion
       ↓
Raw PostgreSQL
       ↓
Curated PostgreSQL
       ↓
FastAPI
       ↓
React
```

This keeps source ingestion separate from application request handling.

---

# 50. Ingestion Architecture

Ingestion is Python application code rather than a public-facing FastAPI endpoint.

Potential project structure:

```text
backend/
├── api/
├── ingestion/
│   ├── baseball_savant/
│   ├── mlb_stats/
│   ├── loaders/
│   └── pipelines/
├── domain/
├── database/
└── ...
```

The ingestion system can later be executed:

- Manually
- Through Docker
- As a scheduled job
- Through AWS EventBridge
- Through ECS
- Through Lambda where appropriate
- Through AWS Batch where appropriate

The initial implementation remains local.

---

# 51. Analytics Architecture

The analytics schema initially favors:

```text
SQL views
+
materialized views when justified
```

rather than creating large numbers of duplicate analytical tables.

Examples of future analytical views:

```text
player_season_batting
player_game_batting
pitcher_game_performance
pitch_type_usage
pitch_type_effectiveness
stadium_batted_ball_analysis
player_pre_post_injury_performance
```

These are analytical concepts, not necessarily physical tables.

The project should first demonstrate that a calculation is useful before materializing it.

---

# 52. V1 Design Principles

The physical schema follows these principles:

## 1. Grain first

Every table has a clearly defined grain.

## 2. Avoid redundant storage

Store an authoritative fact in one appropriate location whenever possible.

## 3. Preserve source data

The raw layer preserves source information even when it is not modeled in curated.

## 4. Curate deliberately

The curated layer represents the baseball domain rather than copying the source schema.

## 5. Prefer derivation

Calculate statistics when practical.

## 6. Use controlled vocabularies

Use reference entities where uncontrolled values would create inconsistency.

## 7. Avoid over-normalization

Not every baseball concept requires an entity.

## 8. Keep future complexity out of V1

Potentially useful future models should be introduced when actual requirements justify them.

## 9. Enforce integrity

Use PostgreSQL constraints for important relational rules.

## 10. Keep business logic explicit

Rules that cannot be naturally enforced by relational constraints belong in ingestion/curation logic.

---

# 53. Deferred Domain Concepts

The following concepts have intentionally been deferred from V1:

```text
TeamSeason
League history
Division history
Historical stadium dimensions
GameParticipant / GameAssociate
Detailed pitcher usage history
GamePlayerPosition
Batting order
BattedBall entity
PlayEvent entity
Swing/BatTracking entity
Detailed fielding events
Season statistics tables
Game statistics tables
Player-team temporal history tables beyond current requirements
```

These are not rejected concepts.

They are deferred until an actual analytical or application requirement justifies them.

---

# 54. Reference Entities Discussed for Future Expansion

Project 1 discussed additional controlled entities such as:

```text
League
Division
PositionType
```

These are not included in the current V1 physical reference schema.

The current V1 reference schema contains only:

```text
game_type
pitch_type
pitch_result
event_type
hand
```

If League, Division, or PositionType becomes necessary to support a concrete domain requirement, they can be added through a deliberate schema change.

---

# 55. Relationship Overview

The primary relational structure is:

```text
                 reference
                    │
          ┌─────────┼──────────┐
          ↓         ↓          ↓
     game_type   event_type   hand
          │         │          │
          ↓         ↓          ↓
        game ←── season       player
          │                    │
          │                    │
          ↓                    │
      game_team ───────────────┘
          │
          ↓
      game_player
          │
          ↓
  plate_appearance
          │
          ↓
        pitch
```

More specifically:

```text
season ───────────────→ game
game_type ────────────→ game
stadium ──────────────→ game

game ─────────────────→ game_team
team ─────────────────→ game_team

game_team ────────────→ game_player
player ───────────────→ game_player

game ─────────────────→ plate_appearance
game_player ──────────→ plate_appearance
event_type ───────────→ plate_appearance
hand ─────────────────→ plate_appearance

plate_appearance ─────→ pitch
pitch_type ───────────→ pitch
pitch_result ─────────→ pitch
```

The most important hierarchy is:

```text
Game
  ↓
GameTeam
  ↓
GamePlayer
  ↓
PlateAppearance
  ↓
Pitch
```

---

# 56. V1 Index Strategy

Indexes should support common access paths without creating unnecessary write overhead.

Current explicitly locked indexes include:

## Game

```sql
CREATE INDEX idx_game_game_date
    ON curated.game (game_date);

CREATE INDEX idx_game_season_id
    ON curated.game (season_id);
```

## GameTeam

```sql
CREATE INDEX idx_game_team_team_id
    ON curated.game_team (team_id);
```

## GamePlayer

```sql
CREATE INDEX idx_game_player_player_id
    ON curated.game_player (player_id);
```

## PlateAppearance

```sql
CREATE INDEX idx_plate_appearance_batter_game_player_id
    ON curated.plate_appearance (batter_game_player_id);

CREATE INDEX idx_plate_appearance_pitcher_game_player_id
    ON curated.plate_appearance (pitcher_game_player_id);
```

## Pitch

```sql
CREATE INDEX idx_pitch_plate_appearance_id
    ON curated.pitch (plate_appearance_id);

CREATE INDEX idx_pitch_pitch_type_id
    ON curated.pitch (pitch_type_id);

CREATE INDEX idx_pitch_pitch_result_id
    ON curated.pitch (pitch_result_id);
```

Unique constraints automatically provide useful indexes where appropriate.

Additional indexes should be introduced based on observed query patterns rather than added speculatively.

---

# 57. Source-to-Curated Identity Strategy

External source identifiers are retained separately from internal IDs.

Examples:

```text
MLBAM player ID
       ↓
curated.player.mlbam_id
       ↓
curated.player.player_id
```

```text
MLB game_pk
       ↓
curated.game.game_pk
       ↓
curated.game.game_id
```

```text
MLB venue ID
       ↓
curated.stadium.mlbam_venue_id
       ↓
curated.stadium.stadium_id
```

This allows the application to maintain stable internal relationships while preserving the source's identity.

---

# 58. Source Data Preservation

The raw layer remains the source of truth for source-specific details.

When a source field is intentionally excluded from curated, it is not necessarily discarded.

The field may remain available through:

```text
raw table
```

and/or:

```text
source_payload JSONB
```

This provides an escape hatch for future modeling without requiring the original source data to be downloaded again.

---

# 59. Data Quality Philosophy

The project should distinguish between:

```text
invalid database state
```

and:

```text
unexpected but potentially legitimate source data
```

Database constraints should prevent clearly invalid states.

Examples:

```text
negative pitch number
negative attendance
invalid hand reference
invalid HOME/AWAY value
invalid pitch count
```

The system should avoid excessive assumptions about real-world baseball measurements until source distributions are understood.

For example, arbitrary limits on:

```text
release speed
launch angle
spin rate
acceleration
```

are intentionally not enforced in V1.

---

# 60. Future AWS Deployment

The initial physical schema is designed for local PostgreSQL.

AWS deployment is intentionally deferred until the project has sufficient application value to justify deployment.

Potential future architecture:

```text
React
  ↓
AWS-hosted application
  ↓
FastAPI
  ↓
PostgreSQL / Amazon RDS
  ↑
Ingestion jobs
```

The physical schema is designed so that moving PostgreSQL from local infrastructure to a managed PostgreSQL environment does not require redesigning the domain model.

---

# 61. Implementation Order

Once the physical schema is locked, implementation should proceed in this order:

```text
1. Create PostgreSQL database
        ↓
2. Create schemas
        ↓
3. Create reference tables
        ↓
4. Seed reference data
        ↓
5. Create raw tables
        ↓
6. Create curated core tables
        ↓
7. Create relationships and indexes
        ↓
8. Create Alembic migration
        ↓
9. Validate schema
        ↓
10. Implement ingestion
        ↓
11. Load raw source data
        ↓
12. Curate into domain tables
        ↓
13. Build analytics
        ↓
14. Expose through FastAPI
        ↓
15. Build React UI
```

The physical database should be validated before building the ingestion pipeline.

---

# 62. Current V1 Status

The following physical schema decisions are locked:

```text
PostgreSQL
├── reference
│   ├── game_type
│   ├── pitch_type
│   ├── pitch_result
│   ├── event_type
│   └── hand
│
├── raw
│   ├── ingestion_batch
│   ├── game_metadata
│   ├── player_metadata
│   ├── team_metadata
│   └── statcast_pitch
│
├── curated
│   ├── season
│   ├── team
│   ├── player
│   ├── stadium
│   ├── game
│   ├── game_team
│   ├── game_player
│   ├── plate_appearance
│   └── pitch
│
└── analytics
    └── views/materialized views initially
```

The curated dependency chain is:

```text
Season
Team
Player
Stadium
   ↓
Game
   ↓
GameTeam
   ↓
GamePlayer
   ↓
PlateAppearance
   ↓
Pitch
```

The raw layer remains source-oriented and independent of curated foreign keys.

The reference layer provides controlled vocabulary.

The analytics layer derives higher-level statistics without unnecessarily duplicating authoritative source facts.

---

# 63. Final Physical Schema Principle

The overall design can be summarized as:

> Preserve the source faithfully, model the baseball domain deliberately, store each authoritative fact at the appropriate grain, enforce important integrity rules in PostgreSQL, and calculate derived statistics when practical.

The physical schema should remain intentionally simple until real analytical requirements demonstrate that additional entities, relationships, or materialized data are necessary.
