-- Partitioning Strategy for Audit and Event Tables
-- 
-- This file documents the PostgreSQL partitioning approach for the
-- game_events and audit_logs tables to enable efficient semester-based
-- data management and cleanup.
--
-- IMPORTANT: These SQL commands should be run after the initial migration
-- creates the base tables. Future migrations can reference this pattern.

-- =====================================================================
-- GAME EVENTS TABLE PARTITIONING
-- =====================================================================

-- Convert game_events to a partitioned table by semester_id
-- This allows efficient querying within a semester and easy cleanup
-- when a semester ends.

-- Example partition creation for a specific semester:
/*
CREATE TABLE game_events_2024_fall PARTITION OF game_events
FOR VALUES FROM ('550e8400-e29b-41d4-a716-446655440001') 
TO ('550e8400-e29b-41d4-a716-446655440002');

-- Create indexes on partition (these are not inherited)
CREATE INDEX idx_game_events_2024_fall_semester_created 
    ON game_events_2024_fall(semester_id, created_at);
CREATE INDEX idx_game_events_2024_fall_type_severity 
    ON game_events_2024_fall(event_type, severity);
CREATE INDEX idx_game_events_2024_fall_company_turn 
    ON game_events_2024_fall(company_id, turn_id);
CREATE INDEX idx_game_events_2024_fall_correlation 
    ON game_events_2024_fall(correlation_id);
CREATE INDEX idx_game_events_2024_fall_event_data 
    ON game_events_2024_fall USING gin(event_data);
*/

-- =====================================================================
-- AUDIT LOGS TABLE PARTITIONING
-- =====================================================================

-- Similarly partition audit_logs by semester_id
/*
CREATE TABLE audit_logs_2024_fall PARTITION OF audit_logs
FOR VALUES FROM ('550e8400-e29b-41d4-a716-446655440001') 
TO ('550e8400-e29b-41d4-a716-446655440002');

-- Create indexes on partition
CREATE INDEX idx_audit_logs_2024_fall_entity_lookup 
    ON audit_logs_2024_fall(entity_type, entity_id, created_at);
CREATE INDEX idx_audit_logs_2024_fall_semester_entity 
    ON audit_logs_2024_fall(semester_id, entity_type, created_at);
CREATE INDEX idx_audit_logs_2024_fall_company_created 
    ON audit_logs_2024_fall(company_id, created_at);
CREATE INDEX idx_audit_logs_2024_fall_user_changes 
    ON audit_logs_2024_fall(changed_by_user_id, created_at);
CREATE INDEX idx_audit_logs_2024_fall_changed_fields 
    ON audit_logs_2024_fall USING gin(changed_fields);
CREATE INDEX idx_audit_logs_2024_fall_context_metadata 
    ON audit_logs_2024_fall USING gin(context_metadata);
*/

-- =====================================================================
-- AUTOMATED PARTITION MANAGEMENT
-- =====================================================================

-- Function to create partitions for a new semester
CREATE OR REPLACE FUNCTION create_semester_audit_partitions(
    p_semester_id UUID,
    p_semester_code TEXT
) RETURNS VOID AS $$
DECLARE
    v_next_semester_id UUID;
    v_partition_name TEXT;
BEGIN
    -- Generate a UUID that's guaranteed to be greater than p_semester_id
    -- This is a simplified approach - in production you might use a different strategy
    v_next_semester_id := gen_random_uuid();
    
    -- Create game_events partition
    v_partition_name := 'game_events_' || lower(replace(p_semester_code, ' ', '_'));
    EXECUTE format(
        'CREATE TABLE %I PARTITION OF game_events FOR VALUES FROM (%L) TO (%L)',
        v_partition_name,
        p_semester_id,
        v_next_semester_id
    );
    
    -- Create indexes for game_events partition
    EXECUTE format('CREATE INDEX %I ON %I(semester_id, created_at)', 
        'idx_' || v_partition_name || '_semester_created', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I(event_type, severity)', 
        'idx_' || v_partition_name || '_type_severity', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I(company_id, turn_id)', 
        'idx_' || v_partition_name || '_company_turn', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I(correlation_id)', 
        'idx_' || v_partition_name || '_correlation', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I USING gin(event_data)', 
        'idx_' || v_partition_name || '_event_data', v_partition_name);
    
    -- Create audit_logs partition
    v_partition_name := 'audit_logs_' || lower(replace(p_semester_code, ' ', '_'));
    EXECUTE format(
        'CREATE TABLE %I PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)',
        v_partition_name,
        p_semester_id,
        v_next_semester_id
    );
    
    -- Create indexes for audit_logs partition
    EXECUTE format('CREATE INDEX %I ON %I(entity_type, entity_id, created_at)', 
        'idx_' || v_partition_name || '_entity_lookup', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I(semester_id, entity_type, created_at)', 
        'idx_' || v_partition_name || '_semester_entity', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I(company_id, created_at)', 
        'idx_' || v_partition_name || '_company_created', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I(changed_by_user_id, created_at)', 
        'idx_' || v_partition_name || '_user_changes', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I USING gin(changed_fields)', 
        'idx_' || v_partition_name || '_changed_fields', v_partition_name);
    EXECUTE format('CREATE INDEX %I ON %I USING gin(context_metadata)', 
        'idx_' || v_partition_name || '_context_metadata', v_partition_name);
    
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- CLEANUP STRATEGY
-- =====================================================================

-- Function to archive and drop semester partitions
CREATE OR REPLACE FUNCTION archive_semester_audit_data(
    p_semester_code TEXT,
    p_archive_schema TEXT DEFAULT 'archive'
) RETURNS VOID AS $$
DECLARE
    v_partition_name TEXT;
BEGIN
    -- Ensure archive schema exists
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', p_archive_schema);
    
    -- Move game_events partition to archive schema
    v_partition_name := 'game_events_' || lower(replace(p_semester_code, ' ', '_'));
    EXECUTE format('ALTER TABLE %I SET SCHEMA %I', v_partition_name, p_archive_schema);
    
    -- Move audit_logs partition to archive schema
    v_partition_name := 'audit_logs_' || lower(replace(p_semester_code, ' ', '_'));
    EXECUTE format('ALTER TABLE %I SET SCHEMA %I', v_partition_name, p_archive_schema);
    
    -- Optionally, you could dump to S3 or other storage and then drop:
    -- EXECUTE format('DROP TABLE %I.%I', p_archive_schema, v_partition_name);
    
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- USAGE EXAMPLES
-- =====================================================================

/*
-- When creating a new semester:
INSERT INTO semesters (id, name, code, ...) VALUES 
    ('550e8400-e29b-41d4-a716-446655440001', 'Fall 2024', 'F24', ...);

-- Create partitions for the semester:
SELECT create_semester_audit_partitions(
    '550e8400-e29b-41d4-a716-446655440001'::UUID, 
    'F24'
);

-- At end of semester, archive the data:
SELECT archive_semester_audit_data('F24');

-- To query events for a specific semester (partition pruning happens automatically):
SELECT * FROM game_events 
WHERE semester_id = '550e8400-e29b-41d4-a716-446655440001'
AND event_type = 'turn.completed';

-- To get audit trail for a specific entity:
SELECT * FROM audit_logs
WHERE entity_type = 'company' 
AND entity_id = '...'
ORDER BY created_at DESC;
*/

-- =====================================================================
-- NOTES
-- =====================================================================

-- 1. Partitioning by semester_id provides natural data isolation
-- 2. Queries within a semester benefit from partition pruning
-- 3. Dropping old semesters is a simple partition drop operation
-- 4. Consider using pg_partman extension for automated partition management
-- 5. Monitor partition sizes - may need sub-partitioning for very large semesters
-- 6. Remember that constraints on partitioned tables are inherited by partitions 