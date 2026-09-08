# Baseball Intelligence Platform — Domain Model

## 1. Purpose

This document defines the curated domain model for the Baseball Intelligence Platform.

The purpose of the domain model is to establish:

- The entities represented by the platform
- The authoritative grain of each entity
- Relationships between entities
- Stored versus derived data
- Database integrity rules
- Domain and pipeline validation rules
- Intentional modeling boundaries
- Future extension points

The domain model is designed to support baseball analytics while avoiding unnecessary complexity and preserving the ability to extend the platform as new analytical requirements emerge.

This document represents the decisions made for **Project 1** of the Baseball Intelligence Platform.

---

# 2. Domain Modeling Principles

The domain model follows these principles.

## 2.1 Store facts at their authoritative grain

Authoritative facts are stored at the natural grain at which they are known.

Examples:

- One row per game
- One row per team per game
- One row per player
- One row per game participant
- One row per plate appearance
- One row per pitch

Values that can be reliably calculated from authoritative facts are generally derived rather than redundantly stored.

> **Store authoritative facts at their natural grain; derive values that can be reliably calculated from those facts. Materialized derived aggregates may be introduced later for performance, but the underlying curated facts remain the source of truth.**

---

## 2.2 Raw source truth versus curated domain truth

The Raw layer preserves the source representation.

The Curated layer represents the standardized domain model.

```text
Source
  ↓
Raw
  ↓
Validation / Transformation
  ↓
Curated
```

Raw data should preserve the complete source record, including fields that are not currently used by the curated model.

The curated layer should contain standardized fields and relationships required by the domain.

This allows the platform to evolve without losing source information.

---

## 2.3 Avoid redundant derived facts

The model should avoid storing values that can be deterministically derived from authoritative facts.

Examples of derived values include:

- Game duration
- Winning team
- Losing team
- Run differential
- Batting team
- Pitcher handedness
- Player age
- Attendance percentage
- Extra-inning status
- Base occupancy booleans
- Advanced metrics such as barrel rate, hard-hit rate, xBA, xSLG, and xwOBA

Materialized aggregates may be introduced later if demonstrated performance requirements justify them.

Materialization is an optimization, not a second source of truth.

---

## 2.4 Entities require meaningful identity or analytical value

A concept is not made into an entity simply because it is a noun in the baseball domain.

An entity should have meaningful:

- Identity
- Grain
- Relationships
- Attributes
- Or independent analytical value

Relationship entities are appropriate when the relationship itself has meaningful attributes or temporal/analytical significance.

---

## 2.5 Database integrity versus domain validation

PostgreSQL is responsible for structural integrity and simple deterministic rules.

The FastAPI/domain and data-validation layers are responsible for more complex business rules.

```text
PostgreSQL
    ↓
Structural integrity

FastAPI / Domain Layer
    ↓
Cross-record and business rules

Data Pipeline
    ↓
Source validation, sequencing, reconciliation, quarantine
```

The general rule is:

> **PostgreSQL enforces structural integrity and simple deterministic constraints. The FastAPI/domain and data-validation layers enforce cross-record, temporal, sequential, and baseball-specific business rules.**

---

# 3. Domain Entities

## 3.1 Season

### Grain

One row per MLB season.

### Purpose

Represents the season-level context within which games and other baseball activity occur.

### Attributes

```text
season_id
season_year
all_star_date
trade_deadline_date
```

Additional season-level attributes may be added as requirements emerge.

### Relationships

```text
Season 1 ──── * Game
```

### Rationale

Season is a first-class entity because season-level context has independent analytical meaning.

---

# 4. Game Domain

## 4.1 Game

### Grain

One row per game.

### Attributes

```text
game_id
season_id
game_type_id
stadium_id
game_status_id

official_game_date
scheduled_start_datetime
actual_start_datetime
actual_end_datetime

temperature
humidity
wind_speed
wind_direction
weather_condition

attendance
```

### Date and time semantics

`official_game_date` represents the official date assigned to the game.

The following timestamps are stored when available:

- Scheduled start
- Actual start
- Actual end

Game duration is derived:

```text
actual_end_datetime - actual_start_datetime
```

A game that crosses midnight remains associated with its official game date.

### Environmental data

Stable physical ballpark characteristics belong to Stadium.

Conditions associated with the individual game belong to Game.

Examples:

```text
Stadium
    capacity
    dimensions
    roof type
    surface type

Game
    temperature
    humidity
    wind
    weather condition
```

Continuous weather observations are intentionally deferred.

### Attendance

Attendance is stored directly on Game.

`NULL` means the value is unavailable or not supplied.

`0` is a legitimate numeric value and is distinct from NULL.

Attendance percentage is derived:

```text
attendance / stadium capacity
```

### Game status

A Game record exists independently of whether baseball events occurred.

Supported statuses:

- Scheduled
- In Progress
- Final
- Postponed
- Suspended
- Cancelled

### Postponed games

A postponed game retains its original Game record.

A subsequently played rescheduled game is represented as its own Game record.

### Suspended games

A suspended game remains one Game.

Additional play continues against the same Game record when the game resumes.

### Cancelled games

A cancelled Game may exist without GamePlayer, PlateAppearance, or Pitch records.

### Extra innings

Extra innings are represented by:

```text
inning_number > 9
```

No ExtraInning entity is required.

### Relationships

```text
Season 1 ──── * Game
Game 1 ──── * GameTeam
Game 1 ──── * GamePlayer
Game 1 ──── * PlateAppearance
Game 1 ──── 1 Stadium
Game 1 ──── 1 GameType
Game 1 ──── 1 GameStatus
```

---

## 4.2 GameTeam

### Grain

One row per team per game.

### Attributes

```text
game_team_id
game_id
team_id
home_away
final_runs
```

### Rules

Every valid game must contain:

- Exactly two teams
- Exactly one Home team
- Exactly one Away team

The database enforces structural rules including:

```text
(game_id, team_id) UNIQUE
(game_id, home_away) UNIQUE
home_away ∈ {HOME, AWAY}
```

The exact-two-team and one-home/one-away requirements are validated by the pipeline/domain layer.

### Derived values

The following are derived rather than stored:

- Winner
- Loser
- Win/loss
- Run differential
- Leading/trailing/tied state

No `winning_team_id` or `losing_team_id` is stored.

### Rationale

GameTeam represents the relationship between a Game and a Team and has meaningful attributes, including home/away designation and final runs.

---

## 4.3 GameType

Reference entity representing the type of game.

Initial vocabulary:

- Regular Season
- All-Star Game
- Wild Card Series
- Division Series
- League Championship Series
- World Series

Detailed historical postseason hierarchy is deferred until required.

---

## 4.4 GameStatus

Reference entity representing the lifecycle status of a Game.

Initial vocabulary:

- Scheduled
- In Progress
- Final
- Postponed
- Suspended
- Cancelled

---

# 5. Team Domain

## 5.1 Team

### Grain

One row per specific historical MLB team identity.

A Team represents the team identity during the relevant historical period rather than the broader franchise.

A relocation or major identity change may result in a new Team record.

### Attributes

```text
team_id
name
city
abbreviation
league_id
division_id
```

### Rationale

A separate Franchise entity is intentionally not included in Project 1.

### Team classification

League and Division are standardized reference entities.

Historical team-to-league/division changes are intentionally deferred.

---

## 5.2 League

Reference entity representing a standardized MLB league.

---

## 5.3 Division

Reference entity representing a standardized MLB division.

---

# 6. Stadium Domain

## 6.1 Stadium

### Grain

One row per distinct physical baseball stadium/ballpark.

The entity represents the physical ballpark rather than commercial naming.

A stadium name change does not create a new Stadium record.

### Attributes

```text
stadium_id
name
city
state
country
latitude
longitude
elevation

roof_type_id
surface_type_id
capacity

left_field_distance
left_center_distance
center_field_distance
right_center_distance
right_field_distance

left_field_wall_height
center_field_wall_height
right_field_wall_height
```

### Units

Curated dimensional measurements are standardized to feet.

No unit column is required in the curated model.

Raw source units and representations are preserved in Raw.

### Historical configuration

Historical stadium configurations are intentionally deferred.

If historical capacity or dimensions become analytically important, a future temporal configuration entity may be introduced.

---

## 6.2 RoofType

Reference entity.

Initial values:

- Open
- Retractable
- Fixed

---

## 6.3 SurfaceType

Reference entity.

Initial values:

- Natural Grass
- Artificial Turf

---

# 7. Player Domain

## 7.1 Player

### Grain

One row per player.

A Player represents the person regardless of whether the player acts as a batter, pitcher, fielder, or other game role.

### Attributes

```text
player_id

first_name
last_name
suffix

date_of_birth

birth_city
birth_state
birth_country

nationality_id

batting_hand
throwing_hand

height
weight
```

### Name

Full name is derived from component fields.

The database does not store a redundant `full_name` field.

### Birth information

Birthplace and nationality are distinct concepts.

A player's birth country does not determine nationality.

### Nationality

Project 1 supports one nationality per Player.

Multiple nationality support is intentionally deferred.

### Handedness

```text
batting_hand
throwing_hand
```

are baseline player attributes.

Allowed batting values:

```text
L
R
S
```

Allowed throwing values:

```text
L
R
```

Actual batter side at a PlateAppearance is stored separately because it represents the side used in that specific PA.

Pitcher handedness is derived from:

```text
PlateAppearance.pitcher_player_id
        ↓
Player.throwing_hand
```

### Height and weight

Height and weight are stored directly on Player for Project 1.

Historical measurement tracking is deferred.

### Player status

Active/inactive status is not stored on Player because status is time-dependent.

---

# 8. Player-Team Domain

## 8.1 PlayerTeamAssignment

### Grain

One row per continuous period of MLB roster membership for a player and team.

### Attributes

```text
player_team_assignment_id
player_id
team_id
start_date
end_date
```

### Date semantics

Both dates are inclusive.

```text
start_date = first day of continuous MLB roster assignment
end_date   = last day of continuous MLB roster assignment
```

`NULL end_date` means the assignment is ongoing.

The database enforces:

```text
end_date IS NULL
OR
end_date >= start_date
```

### Temporal overlap

Overlapping assignments for the same player are validated by the domain/pipeline layer.

### Scope

Project 1 models MLB roster membership.

Transaction details such as:

- Trade
- DFA
- Waiver
- Promotion
- Demotion
- IL placement

are intentionally deferred.

A future PlayerRosterEvent entity may be introduced if those events become analytically important.

### Roster membership versus participation

PlayerTeamAssignment represents roster association.

GamePlayer represents actual game participation.

These concepts are intentionally separate.

### Game participation validation

A GamePlayer team assignment must correspond to a PlayerTeamAssignment covering:

```text
Game.official_game_date
```

The date range is inclusive.

This temporal business rule is validated by the pipeline/domain layer rather than a simple foreign key.

---

# 9. Game Participation Domain

## 9.1 GamePlayer

### Grain

One row per player participating in one game.

### Attributes

```text
game_player_id
game_id
player_id
team_id

started_game
starting_batting_order
starting_position_type_id
```

### Purpose

GamePlayer answers:

> Who participated in the game?

It does not attempt to reconstruct the complete substitution or defensive assignment history.

### Team relationship

`team_id` represents the team for which the player actually participated in the game.

A composite foreign key is used:

```text
GamePlayer
(game_id, team_id)
        ↓
GameTeam
(game_id, team_id)
```

This prevents a player from participating for a team that is not playing in the game.

### Uniqueness

```text
(game_id, player_id) UNIQUE
```

A player can have only one GamePlayer record per game.

### Starting player rules

If:

```text
started_game = true
```

then:

```text
starting_batting_order IS NOT NULL
```

If:

```text
started_game = false
```

then:

```text
starting_batting_order IS NULL
```

The database enforces this conditional rule.

Starting batting-order positions are unique within a team/game.

### Participation versus activity

Not every GamePlayer must have a PlateAppearance.

Examples include:

- Defensive replacements
- Pinch runners
- Players who participate defensively without batting in the available data

---

## 9.2 PositionType

Reference entity representing standardized baseball positions.

Initial values:

- P
- C
- 1B
- 2B
- 3B
- SS
- LF
- CF
- RF
- DH

DH is represented as a position type even though it is not a defensive position.

Detailed defensive assignment history is deferred.

---

# 10. Plate Appearance Domain

## 10.1 PlateAppearance

### Grain

One row per completed pitcher-versus-batter confrontation.

### Attributes

```text
plate_appearance_id

game_id
plate_appearance_number

batter_player_id
pitcher_player_id

batter_side

inning_number
inning_half

outs_before_pa

runner_on_first_player_id
runner_on_second_player_id
runner_on_third_player_id

home_team_score_before_pa
away_team_score_before_pa

outcome_type_id
```

### Relationships

```text
Game 1 ──── * PlateAppearance

Player 1 ──── * PlateAppearance (as batter)
Player 1 ──── * PlateAppearance (as pitcher)

PlateAppearance 1 ──── * Pitch
```

### PA sequence

`plate_appearance_number` is sequential within the entire game.

It does not reset by inning.

The sequence:

```text
1
2
3
4
...
```

is unique within the game.

Database:

```text
(game_id, plate_appearance_number) UNIQUE
```

Pipeline:

- Starts at 1
- Validates sequence continuity

### Inning

```text
inning_number >= 1
inning_half ∈ {TOP, BOTTOM}
```

TOP represents the Away team's half.

BOTTOM represents the Home team's half.

Extra innings are represented by:

```text
inning_number > 9
```

### Outs

`outs_before_pa` stores the game state immediately before the PA.

Valid values:

```text
0
1
2
```

No `outs_after_pa` field is stored.

The database enforces the numeric range.

The pipeline validates inning and out progression.

### Base state

The actual runner occupying each base is stored.

```text
runner_on_first_player_id
runner_on_second_player_id
runner_on_third_player_id
```

NULL means the base is empty.

This allows the model to answer:

> Who was on base when the pitch occurred?

The model does not store redundant boolean fields such as:

```text
runner_on_first = true
runner_on_second = false
```

A player cannot occupy multiple bases simultaneously.

This structural rule may be enforced with database checks, while complete game-state validity is validated by the pipeline.

### Score state

The score immediately before the PA is stored:

```text
home_team_score_before_pa
away_team_score_before_pa
```

Both values must be non-negative.

No score-after fields are stored.

No redundant fields such as:

- run differential
- tied
- leading
- trailing
- batting team score

are stored.

The pipeline validates score progression and reconciliation with GameTeam final runs.

### Batting team

`team_id` is intentionally not stored on PlateAppearance.

The batting team is derived from:

```text
GameTeam + inning_half
```

For example:

```text
TOP    → Away
BOTTOM → Home
```

### Batter and pitcher

Every PA has one batter and one pitcher.

The database prevents:

```text
batter_player_id = pitcher_player_id
```

Batter and pitcher must both have GamePlayer participation records for the same game.

The pipeline validates that the batter and pitcher belong to opposing teams.

### Batter side

`batter_side` represents the actual side used for that PA.

It may differ from a player's baseline switch-hitting designation.

Allowed values:

```text
L
R
```

Pitcher hand is derived from Player.throwing_hand.

### PA outcome

Each PA has exactly one primary/final OutcomeType.

Detailed event reconstruction is intentionally deferred to a future PlayEvent model.

---

# 11. Pitch Domain

## 11.1 Pitch

### Grain

One row per pitch.

This is the fundamental pitch-level analytical grain.

### Attributes

```text
pitch_id
plate_appearance_id
pitch_number

balls_before_pitch
strikes_before_pitch

pitch_type_id
pitch_outcome_type_id

release_speed
release_spin_rate
release_extension
effective_speed
spin_axis

release_pos_x
release_pos_y
release_pos_z

vx0
vy0
vz0

ax
ay
az

pfx_x
pfx_z

plate_x
plate_z

launch_speed
launch_angle
hit_distance
launch_direction

...additional meaningful pitch-level tracking measurements
```

The exact final set of source-specific measurements will be finalized during ingestion/source mapping.

### Pitch sequence

`pitch_number` resets for each PlateAppearance.

Example:

```text
PA 1
  Pitch 1
  Pitch 2
  Pitch 3

PA 2
  Pitch 1
  Pitch 2
```

Database:

```text
(plate_appearance_id, pitch_number) UNIQUE
```

Database also enforces:

```text
pitch_number >= 1
```

Pipeline validates sequence continuity.

### Count

The count before the pitch is stored:

```text
balls_before_pitch
strikes_before_pitch
```

Valid ranges:

```text
balls   = 0–3
strikes = 0–2
```

The database enforces these ranges.

The pipeline validates logical count progression.

No Count entity is required.

### Pitch classification

Every curated pitch requires:

```text
pitch_type_id
pitch_outcome_type_id
```

Missing essential classification is treated as a curated data-quality failure.

The original source classification remains preserved in Raw.

### Physical and tracking measurements

Meaningful pitch-level physical and tracking measurements are represented directly on Pitch.

No one-to-one entities are created for:

- PitchRelease
- PitchMovement
- PitchLocation
- BattedBall
- Trajectory

because these measurements share the Pitch grain and do not have independent identity.

### Nullable measurements

Pitch measurements are nullable when they are:

- Not applicable
- Not observed
- Unavailable from the source

For example, batted-ball measurements are legitimately NULL for a pitch that was not put in play.

### Batted-ball measurements

Available batted-ball physical/tracking measurements are stored directly on Pitch.

Examples include:

```text
launch_speed
launch_angle
hit_distance
launch_direction
```

Additional available trajectory measurements may also be included.

Derived classifications such as:

- Barrel
- Hard hit
- Ground ball
- Fly ball
- Line drive
- Popup
- Sweet spot
- xBA
- xSLG
- xwOBA

are calculated rather than treated as authoritative source facts.

---

# 12. Pitch Classification Domain

## 12.1 PitchType

### Grain

One row per standardized pitch type.

### Attributes

```text
pitch_type_id
code
name
category
```

PitchType answers:

> What was thrown?

The exact standardized taxonomy and source mapping will be finalized during ingestion.

Example conceptual values include:

```text
FF
SI
FC
SL
CU
CH
ST
FS
```

The raw source classification is preserved separately.

---

## 12.2 PitchOutcomeType

### Grain

One row per standardized immediate/final result of a pitch.

### Initial vocabulary

- Ball
- Called Strike
- Swinging Strike
- Foul
- Ball In Play
- Hit By Pitch

PitchOutcomeType answers:

> What happened on this pitch?

It does not represent the final statistical result of the PlateAppearance.

---

## 12.3 OutcomeType

### Grain

One row per standardized primary/final statistical result of a PlateAppearance.

### Initial vocabulary

- Single
- Double
- Triple
- Home Run
- Walk
- Intentional Walk
- Hit By Pitch
- Strikeout
- Groundout
- Flyout
- Lineout
- Popout
- Fielder's Choice
- Reached on Error
- Sacrifice Fly
- Sacrifice Bunt
- Catcher's Interference

OutcomeType answers:

> What was the final statistical result of the PlateAppearance?

It is intentionally not a dumping ground for detailed runner movement, fielding errors, scoring events, or multiple-out sequences.

Those belong in a future PlayEvent model.

---

# 13. Source Identity

## 13.1 SourceIdentityMapping

External source identifiers are integration concerns rather than domain identity.

The platform uses a generalized mapping structure:

```text
SourceIdentityMapping
────────────────────────────
source
entity_type
source_entity_id
domain_entity_id
```

Example:

```text
source = Baseball Savant
entity_type = PLAYER
source_entity_id = 123456
domain_entity_id = 42
```

### Purpose

This allows:

- Multiple sources
- Source-specific identifiers
- Internal domain identities
- Future source expansion

without making external IDs the primary identity of domain entities.

### Entity types

Controlled values may include:

```text
PLAYER
TEAM
GAME
STADIUM
```

Additional entity types may be added as needed.

This is an integration/infrastructure concept rather than a core baseball domain entity.

---

# 14. Runs and Scoring

No Run entity is included in Project 1.

Runs are treated as results of baseball events.

The current model stores:

```text
GameTeam.final_runs
```

and:

```text
PlateAppearance.home_team_score_before_pa
PlateAppearance.away_team_score_before_pa
```

These support game-state and score-based analytics.

Detailed scoring reconstruction is intentionally deferred.

A future PlayEvent model can represent:

- Scoring events
- Runner advancement
- Multiple outs
- Fielding errors
- Other detailed play consequences

---

# 15. Stored Versus Derived Data

## 15.1 Stored authoritative facts

Examples:

- Game dates and timestamps
- Game environmental conditions
- Game attendance
- GameTeam final runs
- Player biographical facts
- PlayerTeamAssignment dates
- GamePlayer participation
- PlateAppearance state before the PA
- Actual batter side
- Pitch classifications
- Pitch measurements
- Runner identities
- Stadium physical characteristics

## 15.2 Derived values

Examples:

- Game duration
- Winner/loser
- Run differential
- Batting team
- Pitcher handedness
- Player age
- Attendance percentage
- Extra-inning status
- Base occupancy flags
- Advanced baseball metrics

The underlying stored facts remain authoritative.

---

# 16. Database Integrity Strategy

## 16.1 Primary keys

All domain entities use internal surrogate primary keys.

Examples:

```text
season_id
game_id
team_id
player_id
stadium_id
game_player_id
plate_appearance_id
pitch_id
```

PostgreSQL owns primary-key enforcement.

---

## 16.2 Foreign keys

Straightforward parent/child relationships are enforced through PostgreSQL foreign keys.

Examples:

```text
Game.season_id → Season.season_id

Game.stadium_id → Stadium.stadium_id

GameTeam.game_id → Game.game_id

GameTeam.team_id → Team.team_id

GamePlayer.game_id → Game.game_id

GamePlayer.player_id → Player.player_id

PlateAppearance.game_id → Game.game_id

PlateAppearance.batter_player_id → Player.player_id

PlateAppearance.pitcher_player_id → Player.player_id

Pitch.plate_appearance_id → PlateAppearance.plate_appearance_id
```

---

## 16.3 Composite foreign keys

Composite relationships are used where they provide important structural integrity.

### GamePlayer → GameTeam

```text
GamePlayer
(game_id, team_id)
        ↓
GameTeam
(game_id, team_id)
```

### GamePlayer identity

```text
GamePlayer
(game_id, player_id)
```

is unique and can serve as the basis for validating PA player participation.

---

## 16.4 Uniqueness

The following business keys are enforced with unique constraints:

```text
GameTeam
(game_id, team_id)

GameTeam
(game_id, home_away)

GamePlayer
(game_id, player_id)

PlateAppearance
(game_id, plate_appearance_number)

Pitch
(plate_appearance_id, pitch_number)
```

---

## 16.5 CHECK constraints

Simple deterministic constraints are enforced by PostgreSQL.

Examples:

```text
inning_number >= 1

outs_before_pa BETWEEN 0 AND 2

balls_before_pitch BETWEEN 0 AND 3

strikes_before_pitch BETWEEN 0 AND 2

pitch_number >= 1

plate_appearance_number >= 1

final_runs >= 0

home_team_score_before_pa >= 0

away_team_score_before_pa >= 0
```

Structural vocabulary constraints include:

```text
inning_half IN ('TOP', 'BOTTOM')

batter_side IN ('L', 'R')

home_away IN ('HOME', 'AWAY')
```

Conditional constraints include:

```text
started_game = true
    → starting_batting_order IS NOT NULL

started_game = false
    → starting_batting_order IS NULL
```

and:

```text
batter_player_id != pitcher_player_id
```

---

# 17. Domain and Pipeline Validation

Not every baseball rule should be implemented as a PostgreSQL constraint.

The pipeline/domain layer validates rules that depend on multiple records, temporal relationships, or ordered game state.

Examples include:

### Game composition

```text
Exactly two GameTeam records
Exactly one Home
Exactly one Away
```

### Player-team temporal membership

```text
GamePlayer.team_id
must correspond to a PlayerTeamAssignment
covering Game.official_game_date
```

### Batter/pitcher relationship

```text
Batter team != Pitcher team
```

### Plate appearance sequence

```text
1, 2, 3, 4, ...
```

### Pitch sequence

```text
1, 2, 3, 4, ...
```

### Count progression

Validate logical transitions between pitches.

### Inning progression

Validate transitions between inning halves and innings.

### Outs progression

Validate the progression of outs throughout the game.

### Score progression

Validate score changes and reconcile final scores with GameTeam.

### Runner state

Validate that runner state is consistent with the game sequence.

### Lineup consistency

Validate:

- Starting lineup completeness
- Valid batting order
- Appropriate positions
- DH rules
- Other source-specific lineup rules

### PA/Pitch cardinality

Every curated PlateAppearance must have at least one Pitch.

Every Pitch must belong to exactly one PlateAppearance.

A zero-pitch PA is treated as a data-quality issue unless a legitimate future source exception is established.

---

# 18. Nullability Strategy

The project uses the following rule:

> **Required fields represent facts necessary to establish the identity, relationship, or essential meaning of a domain record. Nullable fields represent legitimate absence, non-applicability, or unavailable source measurements. Conditional nullability is enforced through database constraints where practical and pipeline validation for more complex baseball rules.**

Examples:

### Required

Core structural fields such as:

```text
Game.season_id
Game.official_game_date

GameTeam.game_id
GameTeam.team_id

GamePlayer.game_id
GamePlayer.player_id

PlateAppearance.game_id
PlateAppearance.batter_player_id
PlateAppearance.pitcher_player_id

Pitch.plate_appearance_id
Pitch.pitch_number
```

### Nullable

Legitimate optional or unavailable information such as:

```text
Game.attendance
Game.temperature
Game.humidity

Player.birth_state
Player.birth_city

PlayerTeamAssignment.end_date

Pitch.launch_speed
Pitch.launch_angle
Pitch.hit_distance
Pitch.release_spin_rate
```

NULL must not be interpreted as zero.

---

# 19. Data Quality Strategy

The platform uses a:

> **Preserve, validate, quarantine**

strategy.

```text
Source
  ↓
Raw
  ↓
Validation
  ├── Valid → Curated
  ├── Valid + Warning → Curated
  └── Invalid/Error → Quarantine
```

The source record is never discarded simply because it fails curated validation.

Missing values may be legitimate.

Essential domain integrity failures are quarantined.

The initial implementation intentionally avoids an elaborate data-quality framework.

A future quality issue structure may include:

```text
source_record_id
field_name
issue_type
description
detected_at
```

---

# 20. Loading and Dependency Strategy

Curated data is loaded in dependency order.

```text
Reference Data
      ↓
Season / Team / Player / Stadium
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

## Reference data

Reference/domain vocabularies are loaded first:

```text
League
Division
GameType
GameStatus
PositionType
PitchType
PitchOutcomeType
OutcomeType
RoofType
SurfaceType
Nationality
```

## Core entities

The following are established before game-event data:

```text
Season
Team
Player
Stadium
```

## Game hierarchy

Game-dependent records are loaded in this order:

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

## Transactions

Curated game loads use database transactions.

Conceptually:

```text
BEGIN TRANSACTION

Insert Game
Insert GameTeam
Insert GamePlayer
Insert PlateAppearance
Insert Pitch
Validate

COMMIT
```

If loading or validation fails:

```text
ROLLBACK
```

This prevents partially loaded curated games.

---

## Deferrable foreign keys

Deferrable foreign keys are **not used initially**.

The domain model has a sufficiently directional dependency structure that normal foreign-key enforcement and dependency-order loading are preferable to deferred constraints.

---

## Raw layer

The Raw layer is not constrained by curated domain relationships.

Raw data exists to preserve source truth and support:

- Auditing
- Debugging
- Reprocessing
- Transformation improvements
- Source comparison

Curated integrity is established after validation and transformation.

---

# 21. Relationship Summary

The core domain relationships are:

```text
Season
  │
  └──< Game
          │
          ├──< GameTeam >── Team
          │
          ├──< GamePlayer >── Player
          │
          └──< PlateAppearance
                    │
                    └──< Pitch
```

Additional relationships:

```text
Team >── League
Team >── Division

Team >── PlayerTeamAssignment <── Player

Game >── Stadium
Game >── GameType
Game >── GameStatus

Stadium >── RoofType
Stadium >── SurfaceType

Player >── Nationality

GamePlayer >── PositionType

Pitch >── PitchType
Pitch >── PitchOutcomeType

PlateAppearance >── OutcomeType
```

---

# 22. Current Domain Model Boundaries

The following are intentionally **not** modeled as Project 1 entities.

| Concept | Decision | Reason |
|---|---|---|
| Franchise | Deferred | Team identity is sufficient for Project 1 |
| TeamSeason | Not required | Current requirements don't justify it |
| GameDate | Not required | Game already owns date semantics |
| GameLocation | Not required | Stadium provides location |
| Attendance | Entity not required | Game-level fact |
| GameScore | Not required | GameTeam owns final runs; PA owns score-before state |
| Run | Deferred | Detailed scoring is event-derived |
| ExtraInning | Not required | `inning_number > 9` |
| ExtraInningRunner | Not required | Runner state represents actual runner |
| Count | Not required | Count belongs to Pitch |
| BatterSide | Not required | Actual side belongs to PA |
| Pitcher | Not required | Pitcher is a Player role |
| Batter | Not required | Batter is a Player role |
| PitchLocation | Not required | Measurements share Pitch grain |
| PitchMovement | Not required | Measurements share Pitch grain |
| PitchRelease | Not required | Measurements share Pitch grain |
| BattedBall | Not required | Measurements share Pitch grain |
| GameLocation | Not required | Stadium already represents physical location |
| StadiumNameHistory | Deferred | Not currently required |
| StadiumConfiguration | Deferred | Historical capacity/dimensions not currently required |
| PlayerMeasurement | Deferred | Historical height/weight not currently required |
| GameWeatherObservation | Deferred | Current game-level weather is sufficient |
| Injury | Deferred | Requires authoritative injury source |
| PlayEvent | Deferred | Required only for detailed event reconstruction |

---

# 23. Future Extension Points

The model intentionally leaves clear extension paths.

## 23.1 PlayEvent

A future PlayEvent model can represent detailed events such as:

- Runner advancement
- Scoring
- Fielding errors
- Multiple outs
- Detailed ball-in-play events
- Complex play reconstruction
- Earned/unearned run analysis

The current model intentionally does not attempt to reconstruct every event from a single PA outcome.

---

## 23.2 Injury

A future Injury model could support:

- Injury dates
- Injury type
- Body part
- Injury status
- IL periods
- Before/after injury analysis

This extension is deferred until an authoritative injury source is selected.

---

## 23.3 Historical stadium configuration

A future StadiumConfiguration model could support:

- Historical capacity
- Historical dimensions
- Wall changes
- Other configuration changes

---

## 23.4 Historical player measurements

A future PlayerMeasurement model could support:

- Measurement date
- Height
- Weight
- Source
- Historical changes

---

## 23.5 Game weather observations

A future GameWeatherObservation model could support:

- Timestamp
- Temperature
- Humidity
- Wind speed
- Wind direction
- Weather conditions

This would allow analysis of changing conditions during a game rather than a game-level snapshot.

---

## 23.6 Detailed roster events

A future PlayerRosterEvent model could represent:

- Trades
- DFA
- Waivers
- Promotions
- Demotions
- IL placement
- Other roster transactions

---

# 24. Attack-the-Model Results

The model was tested against representative baseball scenarios.

| Scenario | Result |
|---|---|
| Player trades | Supported |
| Multiple team assignments | Supported |
| Player doesn't immediately play after trade | Supported |
| Doubleheaders | Supported |
| Games crossing midnight | Supported |
| Postponed games | Supported |
| Cancelled games | Supported |
| Suspended games | Supported at Project 1 granularity |
| Extra innings | Supported |
| Automatic runner | Supported |
| DH | Supported |
| Defensive replacements | Supported at participation level |
| Pinch hitters | Supported |
| Two-way players | Supported |
| Missing tracking data | Supported |
| Foul balls | Supported |
| Walks | Supported |
| Hit by pitch | Supported |
| Home runs | Supported |
| Complex scoring events | Requires future PlayEvent |
| Grand slam event reconstruction | Requires future PlayEvent |
| Multiple outs on one play | Requires future PlayEvent |
| Runner advancement reconstruction | Requires future PlayEvent |
| Earned/unearned run analysis | Requires future event modeling |
| Historical stadium configuration | Future extension |
| Historical weather observations | Future extension |
| Historical player measurements | Future extension |
| Injury analysis | Future extension |

The stress test did not identify a fundamental flaw in the Project 1 domain model.

The limitations identified are intentional boundaries rather than defects.

---

# 25. Domain Model Decision Summary

The Project 1 domain model is based on the following core grains:

```text
Season
    1 row per MLB season

Game
    1 row per game

GameTeam
    1 row per team per game

Team
    1 row per historical team identity

Stadium
    1 row per physical ballpark

Player
    1 row per player

PlayerTeamAssignment
    1 row per continuous player/team roster assignment

GamePlayer
    1 row per player participating in a game

PlateAppearance
    1 row per completed pitcher/batter confrontation

Pitch
    1 row per pitch
```

The model prioritizes:

- Clear grains
- Strong relational integrity
- Historical player/team relationships
- Authoritative facts
- Derived analytics
- Raw source preservation
- Reproducible transformations
- Practical PostgreSQL enforcement
- Pipeline-based baseball validation
- Deliberate avoidance of premature complexity

---

# 26. Final Architecture Principle

The Baseball Intelligence Platform follows this overarching domain-modeling principle:

> **Represent authoritative baseball facts at their natural grain, preserve source truth independently, enforce structural integrity in PostgreSQL, validate complex baseball and temporal rules in the domain/pipeline layers, and introduce additional entities only when real analytical requirements justify them.**

This provides a normalized, extensible foundation for the Baseball Intelligence Platform while preserving a clear path toward more advanced baseball event modeling and analytics.