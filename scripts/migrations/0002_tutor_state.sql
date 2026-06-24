-- D-142 (Phase 2) — Tutor Dialogue State (persistent per-conversation tutor memory).
-- Auto-created on boot by validate_schema_on_startup() (app/core/db_schema_config.py).
-- This standalone DDL is for manual operator use only (Codespaces/Supabase egress is
-- firewalled in the sandbox — apply changes via the boot hook, not from the sandbox).
--
-- One live row per conversation (upsert): the explicit dialogue memory that replaces
-- fragile reconstruct-from-history-text (ISS-117 root cause #5).

CREATE TABLE IF NOT EXISTS "tutor_state" (
    "id"                        SERIAL PRIMARY KEY,
    "conversation_id"           INTEGER NOT NULL UNIQUE,
    "user_id"                   INTEGER NOT NULL REFERENCES "users"("id") ON DELETE CASCADE,
    "active_concept"            VARCHAR(120) NOT NULL DEFAULT '',
    "active_misconception"      VARCHAR(120) NOT NULL DEFAULT '',
    "kc_progress"               TEXT NOT NULL DEFAULT '{}',
    "ability_snapshot"          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    "socratic_count_by_concept" TEXT NOT NULL DEFAULT '{}',
    "last_step_emitted"         TEXT NOT NULL DEFAULT '',
    "turn_count"                INTEGER NOT NULL DEFAULT 0,
    "updated_at"                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "created_at"                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS "ix_tutor_state_conversation_id" ON "tutor_state"("conversation_id");
CREATE INDEX IF NOT EXISTS "ix_tutor_state_user_id" ON "tutor_state"("user_id");
