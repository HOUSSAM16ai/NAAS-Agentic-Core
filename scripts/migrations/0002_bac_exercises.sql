-- Migration 0002 — bac_exercises (Protocol V24.0 — Data Engineering Mandate)
--
-- Strict relational schema for Baccalaureate educational content. Converts the
-- previously unstructured Arabic exercise text (which caused RAG semantic
-- blindness) into rows with strict metadata + a JSONB column for the
-- deterministically parsed entities used by the generative-UI pipeline.
--
-- This DDL is applied AUTOMATICALLY on app startup by
-- app/core/db_schema.py:validate_and_fix_schema() (the table is registered in
-- app/core/db_schema_config.py:REQUIRED_SCHEMA). This file is the standalone
-- equivalent for manual execution against Supabase, e.g.:
--
--   psql "$APP_DATABASE_URL" -f scripts/migrations/0002_bac_exercises.sql
--
-- Or via the ETL driver (recommended — also inserts the BAC 2024 exercise):
--
--   DATABASE_URL="postgresql://...:6543/postgres?sslmode=require" \
--     python live_db_restructure.py

CREATE TABLE IF NOT EXISTS "bac_exercises" (
    "id"               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "subject"          VARCHAR(80)  NOT NULL,          -- e.g. "Math"
    "topic"            VARCHAR(120) NOT NULL,          -- e.g. "Probability"
    "draw_type"        VARCHAR(40),                    -- e.g. "Simultaneous" | "Sequential"
    "year"             INTEGER      NOT NULL
                       CHECK ("year" BETWEEN 1990 AND 2100),  -- e.g. 2024
    "session"          VARCHAR(60),                    -- e.g. "دورة 2024"
    "branch"           VARCHAR(160),                   -- e.g. "Experimental Sciences"
    "exam_ref"         VARCHAR(120),                   -- e.g. "Subject 1"
    "exercise_number"  INTEGER,                        -- e.g. 1
    "language"         VARCHAR(8)   NOT NULL DEFAULT 'ar',
    "source"           VARCHAR(255),                   -- provenance string
    "content_hash"     VARCHAR(64)  NOT NULL UNIQUE,   -- sha256(raw_text) — idempotent upsert key
    "raw_text"         TEXT         NOT NULL,          -- the actual Arabic exercise text
    "parsed_entities"  JSONB        NOT NULL DEFAULT '{}',  -- structured metadata (balls, events, ...)
    "created_at"       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "updated_at"       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS "ix_bac_exercises_subject"
    ON "bac_exercises" ("subject");
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_topic"
    ON "bac_exercises" ("topic");
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_year"
    ON "bac_exercises" ("year");
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_draw_type"
    ON "bac_exercises" ("draw_type");
-- GIN index enables fast containment queries on parsed_entities (RAG filters).
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_parsed_entities"
    ON "bac_exercises" USING GIN ("parsed_entities");
