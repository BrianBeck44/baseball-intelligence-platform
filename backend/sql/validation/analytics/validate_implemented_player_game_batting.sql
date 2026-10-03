SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema = 'analytics'
  AND table_name = 'player_game_batting';


-- 2. Confirm columns and nullability
SELECT
    ordinal_position,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'analytics'
  AND table_name = 'player_game_batting'
ORDER BY ordinal_position;


-- 3. Confirm constraints
SELECT
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'analytics'
  AND table_name = 'player_game_batting'
ORDER BY constraint_type, constraint_name;


-- 4. Confirm foreign keys
SELECT
    tc.constraint_name,
    kcu.column_name,
    ccu.table_schema AS referenced_schema,
    ccu.table_name AS referenced_table,
    ccu.column_name AS referenced_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
   AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON tc.constraint_name = ccu.constraint_name
   AND tc.table_schema = ccu.table_schema
WHERE tc.table_schema = 'analytics'
  AND tc.table_name = 'player_game_batting'
  AND tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.constraint_name, kcu.ordinal_position;


-- 5. Confirm indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'analytics'
  AND tablename = 'player_game_batting'
ORDER BY indexname;


SELECT
    con.conname AS constraint_name,
    src.attname AS source_column,
    ref_ns.nspname AS referenced_schema,
    ref_cls.relname AS referenced_table,
    ref.attname AS referenced_column,
    src_pos.ordinality AS column_position
FROM pg_constraint AS con
JOIN pg_class AS src_cls
    ON src_cls.oid = con.conrelid
JOIN pg_namespace AS src_ns
    ON src_ns.oid = src_cls.relnamespace
JOIN pg_class AS ref_cls
    ON ref_cls.oid = con.confrelid
JOIN pg_namespace AS ref_ns
    ON ref_ns.oid = ref_cls.relnamespace
CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS src_pos(attnum, ordinality)
JOIN pg_attribute AS src
    ON src.attrelid = con.conrelid
   AND src.attnum = src_pos.attnum
CROSS JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS ref_pos(attnum, ordinality)
JOIN pg_attribute AS ref
    ON ref.attrelid = con.confrelid
   AND ref.attnum = ref_pos.attnum
   AND ref_pos.ordinality = src_pos.ordinality
WHERE con.contype = 'f'
  AND src_ns.nspname = 'analytics'
  AND src_cls.relname = 'player_game_batting'
ORDER BY con.conname, src_pos.ordinality;