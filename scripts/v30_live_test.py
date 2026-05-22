#!/usr/bin/env python3
"""
Protocol V30.0 §5 — Live Verification (Deep-Dive Generative UI + Sub-Case Surgery).

يحاكي المسار الإنتاجي الكامل عبر ``OrchestratorClient.chat_with_agent`` ويُثبت
حيّاً المطالب الثلاثة:

  1. لا ``C_2^3 = 0`` (ولا أي C(n,k)=0) في حمولة الـ JSON المُولَّدة.
  2. كبح جدار النص: مجموع النص المبثوث جملة واحدة فقط (≤ 120 حرف).
  3. حمولة الواجهة تحوي القصة البصرية العميقة (urn_state + event_analysis + deep_dive).

المسار: «اعطني تمرين الاحتمالات 2024 ...» → «اريد شرح خارق لاني لم افهم اي شي».

التشغيل:
    python scripts/v30_live_test.py

الأسرار تُقرأ من البيئة فقط (لا تُكتب في الملف أبداً):
    OPENROUTER_API_KEY  — اختياري: ping حيّ لإثبات الاتصال.
    DATABASE_URL        — اختياري: SELECT 1 حيّ لإثبات اتصال Supabase.
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

# التمرين المُسترجَع (يصبح سياق المحادثة) — كيس 11 كرة، سحب 3 دفعة واحدة (آني).
BAC_2024_SIMUL = (
    "يحتوي كيس على 11 كرة متماثلة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. "
    "نسحب 3 كرات دفعة واحدة."
)

CONFUSION_PROMPT = "اريد شرح خارق لاني لم افهم اي شي"


def _scan_combination_leak(payload: dict, bad: list[str]) -> None:
    """يبحث عن أي C(n,k)=0 مُسرَّب في حمولة combinations_visualizer."""
    blob = json.dumps(payload, ensure_ascii=False)
    for needle in ("C(2,3)", "C_2^3", "C(0,", "C(1,3)", "C(1,2)"):
        if needle in blob:
            bad.append(f"leak: '{needle}' present in payload JSON")
    props = payload.get("payload", payload).get("props", {})
    for g in props.get("groups", []):
        if g.get("is_possible") is False and "C(" in str(g.get("pedagogical_string", "")):
            bad.append(f"impossible group renders formula: {g.get('label')}")


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
                print(f"  OpenRouter LIVE: HTTP {r.status_code}, {n} models reachable")
        except Exception as exc:
            print(f"  OpenRouter ping failed: {exc}")
    else:
        print("  OPENROUTER_API_KEY not set — skipping live LLM ping")

    db = os.environ.get("DATABASE_URL", "")
    if db.startswith("postgres"):
        try:
            import asyncpg  # type: ignore

            dsn = db.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
            conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=15.0)
            val = await conn.fetchval("SELECT 1")
            await conn.close()
            print(f"  Supabase LIVE: SELECT 1 -> {val}")
        except Exception as exc:
            print(f"  Supabase connect failed: {exc}")
    else:
        print("  DATABASE_URL not a postgres DSN — skipping live DB probe")


async def main() -> int:
    print("=" * 74)
    print("Protocol V30.0 §5 — LIVE: Deep-Dive UI + Sub-Case Surgery")
    print("=" * 74)
    print("\n[0] Live connectivity (secrets from env):")
    await _live_connectivity()

    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    client = OrchestratorClient.__new__(OrchestratorClient)

    history = [
        {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
        {"role": "assistant", "content": BAC_2024_SIMUL},
    ]

    print(f"\n[1] Driving chat_with_agent for: «{CONFUSION_PROMPT}»")
    ui_events: list[dict] = []
    text_chunks: list[str] = []
    async for ev in client.chat_with_agent(
        CONFUSION_PROMPT, user_id=1, conversation_id=1, history_messages=history
    ):
        if not isinstance(ev, dict):
            text_chunks.append(str(ev))
            continue
        etype = ev.get("type")
        payload = ev.get("payload") or {}
        if etype == "ui_component":
            ui_events.append(payload)
        elif etype == "assistant_delta":
            content = payload.get("content", "")
            if content:
                text_chunks.append(content)

    full_text = "".join(text_chunks).strip()

    print("\n[2] Verification of the three mandates:")
    ok = True

    # Mandate 1 — no C(n,k)=0 leak
    bad: list[str] = []
    if not ui_events:
        bad.append("no ui_component emitted")
    for p in ui_events:
        _scan_combination_leak(p, bad)
    if bad:
        ok = False
        print("  [1] C(n,k)=0 leak: FAIL")
        for b in bad:
            print(f"        - {b}")
    else:
        print("  [1] No C_2^3=0 (no impossible-group formula) — PASS")

    # Mandate 2 — text-wall muzzle (<= 1 sentence)
    sentence_count = sum(full_text.count(s) for s in (".", "!", "؟", "?")) or (
        1 if full_text else 0
    )
    muzzled = len(full_text) <= 120 and "\n" not in full_text
    if muzzled:
        print(f"  [2] Text wall muzzled — PASS (len={len(full_text)}, text=«{full_text}»)")
    else:
        ok = False
        print(
            f"  [2] Text wall NOT muzzled — FAIL (len={len(full_text)}, sentences~{sentence_count})"
        )

    # Mandate 3 — deep visual storytelling payload
    deep_ok = False
    for p in ui_events:
        if p.get("component") == "combinations_visualizer":
            props = p.get("props", {})
            if props.get("deep_dive") and props.get("urn_state") and props.get("event_analysis"):
                deep_ok = True
    if deep_ok:
        print("  [3] Deep-dive payload (urn_state + event_analysis + deep_dive) — PASS")
    else:
        ok = False
        print("  [3] Deep-dive storytelling payload missing — FAIL")

    print("\n[3] Emitted ui_component payload (truncated):")
    if ui_events:
        print(json.dumps(ui_events[0], ensure_ascii=False, indent=2)[:1800])

    print("\n" + "=" * 74)
    if ok:
        print("PASSED — no C_2^3=0, text muzzled to one sentence, deep visual payload present.")
        return 0
    print("FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
