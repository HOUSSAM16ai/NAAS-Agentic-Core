#!/usr/bin/env python3
"""Protocol V24.0 — Live ETL: restructure BAC content into a strict relational schema.

This is the "live ammo" data-engineering driver. It:

  1. Connects to the live Supabase Postgres (read from the environment — never
     hard-coded, so this file is safe to commit).
  2. Creates / updates the ``bac_exercises`` table with strict metadata columns
     + a ``parsed_entities`` JSONB column (the canonical DDL also lives in
     ``app/core/db_schema_config.py:REQUIRED_SCHEMA`` and
     ``scripts/migrations/0002_bac_exercises.sql``).
  3. Upserts the BAC 2024 Mathematics (Experimental Sciences) Probability
     exercise using the strict metadata structure.
  4. Prints the success response returned by the database.

Usage::

    export DATABASE_URL="postgresql://postgres.<ref>:<pw>@aws-1-eu-west-3.pooler.supabase.com:6543/postgres?sslmode=require"
    python live_db_restructure.py

Honesty note (CLAUDE.md doctrine — "no fake certainty"): the Codespaces /
sandbox firewall frequently blocks Postgres egress on ports 6543/5432. When
that happens this script reports the connection failure explicitly and exits
non-zero. It never fabricates a successful insert.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

# ---------------------------------------------------------------------------
# Canonical DDL — kept byte-identical to scripts/migrations/0002_bac_exercises.sql
# and app/core/db_schema_config.py:REQUIRED_SCHEMA["bac_exercises"].
# ---------------------------------------------------------------------------
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS "bac_exercises" (
    "id"               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "subject"          VARCHAR(80)  NOT NULL,
    "topic"            VARCHAR(120) NOT NULL,
    "draw_type"        VARCHAR(40),
    "year"             INTEGER      NOT NULL CHECK ("year" BETWEEN 1990 AND 2100),
    "session"          VARCHAR(60),
    "branch"           VARCHAR(160),
    "exam_ref"         VARCHAR(120),
    "exercise_number"  INTEGER,
    "language"         VARCHAR(8)   NOT NULL DEFAULT 'ar',
    "source"           VARCHAR(255),
    "content_hash"     VARCHAR(64)  NOT NULL UNIQUE,
    "raw_text"         TEXT         NOT NULL,
    "parsed_entities"  JSONB        NOT NULL DEFAULT '{}',
    "created_at"       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "updated_at"       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_subject"         ON "bac_exercises" ("subject");
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_topic"           ON "bac_exercises" ("topic");
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_year"            ON "bac_exercises" ("year");
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_draw_type"       ON "bac_exercises" ("draw_type");
CREATE INDEX IF NOT EXISTS "ix_bac_exercises_parsed_entities" ON "bac_exercises" USING GIN ("parsed_entities");
"""

UPSERT_SQL = """
INSERT INTO "bac_exercises" (
    subject, topic, draw_type, year, session, branch, exam_ref,
    exercise_number, language, source, content_hash, raw_text, parsed_entities
) VALUES (
    %(subject)s, %(topic)s, %(draw_type)s, %(year)s, %(session)s, %(branch)s, %(exam_ref)s,
    %(exercise_number)s, %(language)s, %(source)s, %(content_hash)s, %(raw_text)s, %(parsed_entities)s
)
ON CONFLICT (content_hash) DO UPDATE SET
    subject         = EXCLUDED.subject,
    topic           = EXCLUDED.topic,
    draw_type       = EXCLUDED.draw_type,
    year            = EXCLUDED.year,
    session         = EXCLUDED.session,
    branch          = EXCLUDED.branch,
    exam_ref        = EXCLUDED.exam_ref,
    exercise_number = EXCLUDED.exercise_number,
    language        = EXCLUDED.language,
    source          = EXCLUDED.source,
    raw_text        = EXCLUDED.raw_text,
    parsed_entities = EXCLUDED.parsed_entities,
    updated_at      = NOW()
RETURNING id, subject, topic, draw_type, year, created_at, updated_at;
"""

# ---------------------------------------------------------------------------
# The actual BAC 2024 Probability exercise (Arabic raw text).
# ---------------------------------------------------------------------------
RAW_TEXT = (
    "التمرين الأول (04 نقاط) — الاحتمالات\n\n"
    "يحتوي كيس على 11 كرة متماثلة لا تُفرّق باللمس موزعة كما يلي:\n"
    "- كرتان بيضاوان مرقمتان بـ: 1، 3\n"
    "- أربع كرات حمراء مرقمة بـ: 0، 1، 1، 3\n"
    "- خمس كرات خضراء مرقمة بـ: 0، 1، 1، 3، 4\n\n"
    "نسحب عشوائيًا 3 كرات دفعة واحدة من الكيس، ونعتبر الحوادث الآتية:\n"
    "- A: الحصول على 3 كرات من نفس اللون.\n"
    "- B: الحصول على 3 كرات جداء أرقامها عدد فردي.\n"
    "- C: الحصول على 3 كرات جداء أرقامها عدد زوجي.\n\n"
    "(1) احسب احتمال الحادثة P(A)، ثم بيّن أن P(B) = 56/165، ثم استنتج P(C). "
    "ثم احسب الاحتمال الشرطي P_A(B).\n"
    "(2) ليكن X المتغير العشوائي الذي يرافق سحب 3 كرات ويمثل عدد الكرات التي "
    "تحمل رقمًا زوجيًا. عيّن قانون الاحتمال، احسب الأمل الرياضي E(X) و P(X > 1).\n"
    "(II) نسحب الآن 3 كرات على التوالي وبدون إرجاع. احسب احتمال الحادثة D: "
    "الحصول على 3 كرات جداء أرقامها معدوم."
)

# Deterministic parsed entities (mirrors the generative-UI extraction doctrine,
# CLAUDE.md D-074/D-076). This is what makes RAG semantically aware instead of
# blind to the problem structure.
PARSED_ENTITIES = {
    "container": "كيس",
    "total_items": 11,
    "draw_count": 3,
    "draw_type": "simultaneous",
    "with_replacement": False,
    "components": [
        {"entity": "كرة بيضاء", "color": "white", "count": 2, "numbers": [1, 3]},
        {"entity": "كرة حمراء", "color": "red", "count": 4, "numbers": [0, 1, 1, 3]},
        {"entity": "كرة خضراء", "color": "green", "count": 5, "numbers": [0, 1, 1, 3, 4]},
    ],
    "events": [
        {"id": "A", "label": "3 كرات من نفس اللون"},
        {"id": "B", "label": "جداء الأرقام عدد فردي", "known_probability": "56/165"},
        {"id": "C", "label": "جداء الأرقام عدد زوجي"},
        {"id": "D", "label": "جداء الأرقام معدوم", "draw_type": "sequential_without_replacement"},
    ],
    "random_variable": {"name": "X", "meaning": "عدد الكرات التي تحمل رقمًا زوجيًا"},
}

RECORD = {
    "subject": "Math",
    "topic": "Probability",
    "draw_type": "Simultaneous",
    "year": 2024,
    "session": "دورة 2024",
    "branch": "Experimental Sciences",
    "exam_ref": "Subject 1",
    "exercise_number": 1,
    "language": "ar",
    "source": "Bac 2024 Mathematics - Experimental Sciences (Subject 1, Exercise 1)",
    "raw_text": RAW_TEXT,
    "parsed_entities": PARSED_ENTITIES,
}


def resolve_db_url() -> str:
    """Read the connection string from the environment (never hard-coded)."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("APP_DATABASE_URL")
    if not url:
        sys.exit(
            "❌ DATABASE_URL (or APP_DATABASE_URL) is not set.\n"
            "   Export the Supabase connection string before running, e.g.:\n"
            '   export DATABASE_URL="postgresql://...:6543/postgres?sslmode=require"'
        )
    # psycopg2 speaks plain libpq URIs — strip any SQLAlchemy async driver suffix.
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg2://", "postgresql://"
    )


def main() -> int:
    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        sys.exit(
            "❌ psycopg2 is not installed in this environment.\n"
            "   Run inside the orchestrator container or a Codespace where\n"
            "   requirements.txt (psycopg2-binary) is installed, or:\n"
            "   pip install psycopg2-binary"
        )

    db_url = resolve_db_url()
    record = dict(RECORD)
    record["content_hash"] = hashlib.sha256(record["raw_text"].encode("utf-8")).hexdigest()

    safe_host = db_url.split("@")[-1].split("?")[0] if "@" in db_url else "<hidden>"
    print(f"🔌 Connecting to Supabase Postgres @ {safe_host} ...")

    try:
        conn = psycopg2.connect(db_url, connect_timeout=15)
    except Exception as exc:  # surface the real driver error honestly
        print(f"❌ Connection failed: {exc}", file=sys.stderr)
        print(
            "   (In the Codespaces/sandbox firewall, Postgres egress on ports\n"
            "    6543/5432 is commonly blocked — run this where egress is open.)",
            file=sys.stderr,
        )
        return 2

    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            print("🏗️  Ensuring strict schema (bac_exercises) ...")
            cur.execute(CREATE_TABLE_SQL)

            print("📥 Upserting BAC 2024 Probability exercise ...")
            params = dict(record, parsed_entities=Json(record["parsed_entities"]))
            cur.execute(UPSERT_SQL, params)
            row = cur.fetchone()
            cols = [d.name for d in cur.description]

            cur.execute('SELECT COUNT(*) FROM "bac_exercises";')
            total = cur.fetchone()[0]
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"❌ ETL failed (rolled back): {exc}", file=sys.stderr)
        return 3
    finally:
        conn.close()

    print("\n✅ DATABASE SUCCESS RESPONSE")
    print(
        json.dumps(
            dict(zip(cols, (str(v) for v in row), strict=False)),
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"\n📊 bac_exercises total rows: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
