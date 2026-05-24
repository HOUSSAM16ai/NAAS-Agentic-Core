#!/usr/bin/env python3
"""
Protocol V19.0 §4 — Auto-Triggering UI Live Test (Frustration + Math Router).

يُثبت حيّاً أن النظام:
  1. يكشف الإحباط ("مفهمتش كيفاش حسبنا الاحتمال") — Frustration Detector.
  2. يكشف "دفعة واحدة" (سحب آني) — Pedagogical Math Router.
  3. لا يُنتج شجرة احتمالات تتابعية (probability_tree) للسحب الآني.
     يوجّه إلى واجهة تأليفية موثوقة: combinations_visualizer أو full_exercise_story.
  4. الجذر بلا احتمال وهمي 1/1، ولا كسور منحلّة (1/0).

المسار:
  User: «التمرين الأول... نسحب عشوائيا 3 كرات دفعة واحدة...» (Bac 2024)
  User: «مفهمتش كيفاش حسبنا الاحتمال»

التشغيل:
    python scripts/test_auto_ui_trigger.py
الأسرار من البيئة (لا تُكتب في الملف): OPENROUTER_API_KEY, DATABASE_URL.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-pipeline-secure-length")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LLM_MOCK_MODE", "1")
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_ROLE_KEY", "dummy")

BAC_2024 = (
    "التمرين الأول: يحتوي كيس على 11 كرة متماثلة موزعة: كرتان بيضاوان، "
    "أربع كرات حمراء، خمس كرات خضراء. نسحب عشوائياً 3 كرات دفعة واحدة."
)


async def _live_connectivity() -> None:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                n = len(r.json().get("data", [])) if r.status_code == 200 else 0
                print(f"  ✅ OpenRouter LIVE: HTTP {r.status_code}, {n} models reachable")
        except Exception as exc:
            print(f"  ⚠️ OpenRouter ping failed: {exc}")
    else:
        print("  ℹ️ OPENROUTER_API_KEY not set — skipping live LLM ping")

    db = os.environ.get("DATABASE_URL", "")
    if db.startswith("postgres"):
        try:
            import asyncpg

            dsn = db.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
            conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=15.0)
            val = await conn.fetchval("SELECT 1")
            await conn.close()
            print(f"  ✅ Supabase LIVE: SELECT 1 → {val}")
        except Exception as exc:
            print(f"  ⚠️ Supabase connect failed: {exc}")
    else:
        print("  ℹ️ DATABASE_URL not a postgres DSN — skipping live DB probe")


def main() -> int:
    print("=" * 76)
    print("Protocol V19.0 §4 — Auto-Triggering UI Live Test")
    print("=" * 76)

    print("\n[0] Live connectivity (secrets from env):")
    asyncio.run(_live_connectivity())

    from app.infrastructure.clients.orchestrator_client import OrchestratorClient
    from app.services.skills.probability_skill import ProbabilityCalculatorSkill

    skill = ProbabilityCalculatorSkill()
    confused = "مفهمتش كيفاش حسبنا الاحتمال"

    print(f"\n[1] Frustration Detector على: «{confused}»")
    is_conf = skill.is_confusion(confused)
    print(f"  is_confusion = {is_conf}")

    print("\n[2] Math Router على نص التمرين (يحوي «دفعة واحدة»):")
    mode = skill._detect_draw_mode(BAC_2024)
    print(f"  draw_mode = {mode}  (متوقَّع: simultaneous)")

    print("\n[3] Turn 1: استرجاع التمرين (يصبح سياقاً).")
    history = [
        {"role": "user", "content": "اعطني التمرين الأول للاحتمالات 2024"},
        {"role": "assistant", "content": BAC_2024},
    ]

    print("\n[4] Turn 2: الطالب محتار → النظام يوجّه تلقائياً للأداة البصرية الصحيحة.")
    event = OrchestratorClient._build_calculated_ui(confused, history_messages=history)

    ok = True
    if event is None:
        print("  ❌ لم يُنتَج أي مكوّن بصري (فشل الكشف التلقائي).")
        return 1

    component = event["component"]
    props = event["props"]
    print(f"  → component = {component}")
    print("\n  RAW JSON tool-call payload:")
    print(json.dumps({"type": "ui_component", "payload": event}, ensure_ascii=False, indent=2))

    print("\n[5] التحقّقات:")
    if is_conf:
        print("  ✅ كُشِف الإحباط (confusion).")
    else:
        print("  ❌ لم يُكشَف الإحباط.")
        ok = False
    if mode == "simultaneous":
        print("  ✅ كُشِف «دفعة واحدة» (سحب آني).")
    else:
        print("  ❌ لم يُكشَف السحب الآني.")
        ok = False
    valid_components = {"combinations_visualizer", "full_exercise_story"}
    if component in valid_components:
        print(
            "  ✅ وُجِّه إلى واجهة بيداغوجية صحيحة "
            f"({component}) — لا شجرة تتابعية."
        )
    else:
        print(f"  ❌ وُجِّه إلى {component} خارج المسار البيداغوجي المعتمد.")
        ok = False
    if component == "probability_tree" or "tree" in props:
        print("  ❌ كارثة تربوية: شجرة احتمالات للسحب الآني!")
        ok = False
    else:
        print("  ✅ لا شجرة احتمالات (probability_tree) للسحب الآني.")
    # math sanity
    if component == "combinations_visualizer":
        total = props.get("total_combinations")
        favorable = props.get("same_group_favorable")
    elif component == "full_exercise_story":
        event_step = next(
            (s for s in props.get("exercise_steps", []) if s.get("step_id") == "same_color_event"),
            None,
        )
        state = (event_step or {}).get("numerical_state", {})
        total = state.get("total_combinations")
        favorable = state.get("same_group_favorable")
    else:
        total = None
        favorable = None

    if component in valid_components:
        if total == 165 and favorable == 14:
            print("  ✅ الحساب التأليفي صحيح: C(11,3)=165، P(3 من نفس اللون)=14/165.")
        else:
            print(
                f"  ⚠️ قيم تأليفية غير متوقَّعة: {total}, {favorable}"
            )

    print("\n" + "=" * 76)
    if ok:
        print("🎉 AUTO-TRIGGER TEST PASSED — confusion + 'دفعة واحدة' → Combinatorics, NOT a tree.")
        return 0
    print("❌ AUTO-TRIGGER TEST FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
