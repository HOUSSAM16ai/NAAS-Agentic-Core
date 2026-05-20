"""
Live BKT verification — RUN INSIDE CODESPACES (where Supabase egress is open).

This sandbox blocks Postgres ports 6543/5432, so this proof must run in the
live environment. It:
  1. ensures the student_bkt_analytics table exists (auto-create via schema validator),
  2. runs a real probability question through BKTEngine,
  3. inserts a row via BKTAnalyticsService (append-only),
  4. reads the row back and prints it as proof.

Usage:
    python scripts/verify_bkt_live.py
    python scripts/verify_bkt_live.py --user-id 7 --question "..."

Requires APP_DATABASE_URL / DATABASE_URL in the process environment.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import desc, select

from app.core.database import async_session_factory
from app.core.db_schema import validate_schema_on_startup
from app.core.domain.bkt_analytics import StudentBKTAnalytic
from app.services.analytics.bkt_persistence import BKTAnalyticsService


async def _main(user_id: int, session_id: int | None, question: str) -> None:
    print("→ Step 1: ensuring schema (auto-create student_bkt_analytics) ...")
    await validate_schema_on_startup()

    print(f"→ Step 2/3: evaluating + persisting interaction for user_id={user_id} ...")
    async with async_session_factory() as db:
        evaluation = await BKTAnalyticsService(db).evaluate_and_record(
            user_id=user_id,
            session_id=session_id,
            question=question,
        )
    print("   evaluation:", evaluation.model_dump())

    print("→ Step 3: reading the latest row back from Supabase ...")
    async with async_session_factory() as db:
        stmt = (
            select(StudentBKTAnalytic)
            .where(StudentBKTAnalytic.user_id == user_id)
            .order_by(desc(StudentBKTAnalytic.id))
            .limit(1)
        )
        row = (await db.execute(stmt)).scalar_one_or_none()

    if row is None:
        print("   ❌ NO ROW FOUND — persistence failed.")
        raise SystemExit(1)

    print("   ✅ ROW PERSISTED:")
    print(f"      id={row.id}")
    print(f"      user_id={row.user_id} session_id={row.session_id}")
    print(f"      concept_id={row.concept_id}")
    print(f"      cognitive_load_estimate={row.cognitive_load_estimate}")
    print(f"      student_mastery_probability={row.student_mastery_probability}")
    print(f"      interaction_count={row.interaction_count}")
    print(f"      interaction_timestamp={row.interaction_timestamp}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live BKT persistence verification")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--session-id", type=int, default=None)
    parser.add_argument(
        "--question",
        type=str,
        default="ارسم شجرة الاحتمالات: احتمال سحب كرة حمراء هو 0.3 واحتمال النجاح بشرط الحمراء 0.8",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.user_id, args.session_id, args.question))


if __name__ == "__main__":
    main()
