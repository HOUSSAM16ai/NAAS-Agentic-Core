-- Migration 0001 — student_bkt_analytics (Protocol V6.0 — BKT persistence)
--
-- This DDL is applied AUTOMATICALLY on app startup by
-- app/core/db_schema.py:validate_and_fix_schema() (the table is registered in
-- app/core/db_schema_config.py:REQUIRED_SCHEMA). This file is the standalone
-- equivalent for manual execution against Supabase, e.g.:
--
--   psql "$APP_DATABASE_URL" -f scripts/migrations/0001_student_bkt_analytics.sql
--
-- Append-only interaction log: each student interaction inserts one row; the
-- evolving mastery is read from the most-recent row per (user_id, concept_id).

CREATE TABLE IF NOT EXISTS "student_bkt_analytics" (
    "id"                          SERIAL PRIMARY KEY,
    "user_id"                     INTEGER NOT NULL REFERENCES "users"("id") ON DELETE CASCADE,
    "session_id"                  INTEGER,
    "concept_id"                  VARCHAR(120) NOT NULL,
    "cognitive_load_estimate"     VARCHAR(10) NOT NULL DEFAULT 'medium'
                                  CHECK ("cognitive_load_estimate" IN ('low', 'medium', 'high')),
    "student_mastery_probability" DOUBLE PRECISION NOT NULL DEFAULT 0.0
                                  CHECK ("student_mastery_probability" >= 0.0
                                         AND "student_mastery_probability" <= 1.0),
    "interaction_count"           INTEGER NOT NULL DEFAULT 1,
    "interaction_timestamp"       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "created_at"                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS "ix_student_bkt_analytics_user_id"
    ON "student_bkt_analytics" ("user_id");
CREATE INDEX IF NOT EXISTS "ix_student_bkt_analytics_concept_id"
    ON "student_bkt_analytics" ("concept_id");
CREATE INDEX IF NOT EXISTS "ix_student_bkt_analytics_interaction_timestamp"
    ON "student_bkt_analytics" ("interaction_timestamp");
