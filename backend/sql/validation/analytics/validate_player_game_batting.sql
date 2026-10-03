-- ============================================================================
-- Analytics Validation: player_game_batting
-- ============================================================================
--
-- Purpose:
--   Independently validate the source data and derivation rules for
--   analytics.player_game_batting before and after analytics loads.
--
-- Expected analytics grain:
--   One row per player, per game, per team.
--
-- Source:
--   curated.plate_appearance
--   curated.outcome_type
--   curated.player
--   curated.game
--   curated.team
--   curated.game_team
--
-- These queries intentionally validate the analytics result independently
-- from the analytics table itself.
-- ============================================================================


-- ============================================================================
-- 1. Validate overall batting totals
-- ============================================================================
--
-- Validates:
--   The aggregate batting-stat derivation from curated plate appearances.
--
-- Expected current totals:
--   Plate appearances: 2,500
--   At bats:           2,203
--   Hits:                489
--   Singles:             325
--   Doubles:              98
--   Triples:               5
--   Home runs:            61
--   Walks:               222
--   Hit by pitch:         40
--   Strikeouts:          585
--   Sacrifice flies:      19
--   Sacrifice bunts:       8
--
-- Note:
--   Walks include both walk and intent_walk.
--   Strikeouts include both strikeout and strikeout_double_play.
-- ============================================================================

SELECT
    COUNT(*) AS plate_appearances,

    COUNT(*) FILTER (
        WHERE ot.code IN (
            'single',
            'double',
            'triple',
            'home_run',
            'strikeout',
            'strikeout_double_play',
            'field_out',
            'field_error',
            'force_out',
            'grounded_into_double_play',
            'double_play',
            'fielders_choice',
            'fielders_choice_out'
        )
    ) AS at_bats,

    COUNT(*) FILTER (
        WHERE ot.code IN (
            'single',
            'double',
            'triple',
            'home_run'
        )
    ) AS hits,

    COUNT(*) FILTER (
        WHERE ot.code = 'single'
    ) AS singles,

    COUNT(*) FILTER (
        WHERE ot.code = 'double'
    ) AS doubles,

    COUNT(*) FILTER (
        WHERE ot.code = 'triple'
    ) AS triples,

    COUNT(*) FILTER (
        WHERE ot.code = 'home_run'
    ) AS home_runs,

    COUNT(*) FILTER (
        WHERE ot.code IN ('walk', 'intent_walk')
    ) AS walks,

    COUNT(*) FILTER (
        WHERE ot.code = 'hit_by_pitch'
    ) AS hit_by_pitch,

    COUNT(*) FILTER (
        WHERE ot.code IN ('strikeout', 'strikeout_double_play')
    ) AS strikeouts,

    COUNT(*) FILTER (
        WHERE ot.code = 'sac_fly'
    ) AS sacrifice_flies,

    COUNT(*) FILTER (
        WHERE ot.code = 'sac_bunt'
    ) AS sacrifice_bunts

FROM curated.plate_appearance pa
LEFT JOIN curated.outcome_type ot
    ON ot.id = pa.outcome_type_id;


-- ============================================================================
-- 2. Validate the player/game/team analytics grain
-- ============================================================================
--
-- Validates:
--   The proposed analytics grain of one row per:
--
--       player_id + game_id + batter_team_id
--
-- The number of distinct player/game/team combinations should be the number
-- of rows that the analytics transformation will produce.
--
-- Expected current results:
--   Plate appearances:                    2,500
--   Distinct player/game/team combinations: 672
-- ============================================================================

SELECT
    COUNT(*) AS plate_appearances,

    COUNT(
        DISTINCT (
            pa.batter_id,
            pa.game_id,
            pa.batter_team_id
        )
    ) AS distinct_player_game_team_combinations

FROM curated.plate_appearance pa;


-- ============================================================================
-- 3. Validate player, game, and team foreign-key resolution
-- ============================================================================
--
-- Validates:
--   Every plate appearance can resolve its:
--     - batter/player
--     - game
--     - batter team
--
-- Expected result:
--   unresolved_rows = 0
--
-- This ensures the analytics transformation will not encounter missing
-- dimension records when creating player/game/team batting rows.
-- ============================================================================

SELECT
    COUNT(*) AS unresolved_rows

FROM curated.plate_appearance pa

LEFT JOIN curated.player p
    ON p.player_id = pa.batter_id

LEFT JOIN curated.game g
    ON g.game_id = pa.game_id

LEFT JOIN curated.team t
    ON t.team_id = pa.batter_team_id

WHERE p.player_id IS NULL
   OR g.game_id IS NULL
   OR t.team_id IS NULL;


-- ============================================================================
-- 4. Validate the game/team relationship
-- ============================================================================
--
-- Validates:
--   Every (game_id, team_id) combination produced by the batting analytics
--   grain exists in curated.game_team.
--
-- This directly validates the planned composite foreign key:
--
--   (game_id, team_id)
--       REFERENCES curated.game_team(game_id, team_id)
--
-- Expected result:
--   invalid_game_team_rows = 0
-- ============================================================================

SELECT
    COUNT(*) AS invalid_game_team_rows

FROM (
    SELECT DISTINCT
        pa.game_id,
        pa.batter_team_id AS team_id

    FROM curated.plate_appearance pa
) x

LEFT JOIN curated.game_team gt
    ON gt.game_id = x.game_id
   AND gt.team_id = x.team_id

WHERE gt.game_team_id IS NULL;


-- ============================================================================
-- 5. Validate outcome-to-stat derivation
-- ============================================================================
--
-- Validates:
--   Each authoritative plate appearance outcome maps to the expected
--   batting-stat categories.
--
-- Columns:
--   plate_appearances = every PA
--   at_bats           = outcomes that qualify as AB
--   hits              = single/double/triple/home_run
--
-- This query is intentionally grouped by outcome so that changes or
-- unexpected outcomes can be identified individually.
--
-- Expected current totals across all rows:
--   PA  = 2,500
--   AB  = 2,203
--   H   = 489
-- ============================================================================

SELECT
    COALESCE(ot.code, '<NULL>') AS outcome,

    COUNT(*) AS plate_appearances,

    COUNT(*) FILTER (
        WHERE ot.code IN (
            'single',
            'double',
            'triple',
            'home_run',
            'strikeout',
            'strikeout_double_play',
            'field_out',
            'field_error',
            'force_out',
            'grounded_into_double_play',
            'double_play',
            'fielders_choice',
            'fielders_choice_out'
        )
    ) AS at_bats,

    COUNT(*) FILTER (
        WHERE ot.code IN (
            'single',
            'double',
            'triple',
            'home_run'
        )
    ) AS hits

FROM curated.plate_appearance pa

LEFT JOIN curated.outcome_type ot
    ON ot.id = pa.outcome_type_id

GROUP BY ot.code

ORDER BY plate_appearances DESC;


-- ============================================================================
-- 6. Validate the fundamental hit-count invariant
-- ============================================================================
--
-- Validates:
--   Hits must equal the sum of their individual hit components:
--
--       Hits = Singles + Doubles + Triples + Home Runs
--
-- Expected result:
--   hits = component_hits
--   Both values should equal 489 for the current dataset.
--
-- This protects against future changes to the transformation logic that
-- could cause the aggregate hit count to disagree with its components.
-- ============================================================================

SELECT
    SUM(
        CASE
            WHEN ot.code IN (
                'single',
                'double',
                'triple',
                'home_run'
            )
            THEN 1
            ELSE 0
        END
    ) AS hits,

    SUM(
        CASE
            WHEN ot.code = 'single'
            THEN 1
            ELSE 0
        END
    )
    +
    SUM(
        CASE
            WHEN ot.code = 'double'
            THEN 1
            ELSE 0
        END
    )
    +
    SUM(
        CASE
            WHEN ot.code = 'triple'
            THEN 1
            ELSE 0
        END
    )
    +
    SUM(
        CASE
            WHEN ot.code = 'home_run'
            THEN 1
            ELSE 0
        END
    ) AS component_hits

FROM curated.plate_appearance pa

LEFT JOIN curated.outcome_type ot
    ON ot.id = pa.outcome_type_id;