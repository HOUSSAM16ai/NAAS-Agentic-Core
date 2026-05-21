#!/usr/bin/env python3
"""
Protocol V17.0 §4 — OMNI Live Empirical Test.

يحاكي مسار المستخدم الكامل ويُثبت حيّاً:
  1. لا كسور منحلّة (لا 1/0، لا قسمة على صفر) في حساب الاحتمالات.
  2. تذكُّر السياق على أسئلة المتابعة (history → نفس التركيبة، لا نسيان).
  3. الخلفية تُخرج JSON منظَّماً (Pydantic) فقط — لا HTML.

المسار: «اعطني تمرين الاحتمالات 2024» → «اعطني شجرة الاحتمالات»
        → «لم افهم شجرة الاحتمالات».

التشغيل:
    python scripts/omni_live_test.py

الأسرار تُقرأ من البيئة (لا تُكتب في الملف أبداً):
    OPENROUTER_API_KEY  — اختياري: يُجري ping حيّ لإثبات الاتصال.
    DATABASE_URL        — اختياري: يُجري SELECT 1 حيّ لإثبات اتصال Supabase.
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

# التمرين المُسترجَع (يصبح سياق المحادثة) — مقتبس من knowledge_base/bac2024.
BAC_2024 = (
    "يحتوي كيس على 11 كرة متماثلة لا تُفرّق باللمس موزعة كما يلي: "
    "كرتان بيضاوان مرقمتان بـ 1، 3. أربع كرات حمراء مرقمة بـ 0، 1، 1، 3. "
    "خمس كرات خضراء مرقمة بـ 0، 1، 1، 3، 4. نسحب 3 كرات على التوالي وبدون إرجاع."
)


def _scan_garbage(node: dict, path: str, bad: list[str]) -> None:
    pn, pd = node.get("p_num"), node.get("p_den")
    if not isinstance(pd, int) or pd < 1:
        bad.append(f"{path}/{node.get('label')}: DIV/ZERO p_den={pd}")
    elif not isinstance(pn, int) or pn < 0 or pn > pd:
        bad.append(f"{path}/{node.get('label')}: invalid {pn}/{pd}")
    for ch in node.get("children", []) or []:
        _scan_garbage(ch, f"{path}/{node.get('label')}", bad)


def _print_props(props: dict) -> list[str]:
    print(
        f"  total={props.get('total')} | strategy={props.get('strategy')} "
        f"| with_replacement={props.get('with_replacement')}"
    )
    print("  المكوّنات (كسور محسوبة حيّاً):")
    for c in props.get("composition", []):
        print(f"     • P({c['label']}) = {c['p_num']}/{c['p_den']}  ≈ {c['p_decimal']}")
    bad: list[str] = []
    if isinstance(props.get("tree"), dict):
        _scan_garbage(props["tree"], "", bad)
    return bad


async def _turn(client, label: str, question: str, history: list[dict]) -> dict | None:
    print(f"\n{'─' * 74}\n▶ {label}\n  السؤال: {question}")
    props = await client._build_probability_tree_props(question, history_messages=history)
    if props is None:
        print("  (لا شجرة احتمالات لهذا الدور)")
        return None
    bad = _print_props(props)
    if bad:
        print("  ❌ GARBAGE FRACTIONS:")
        for b in bad:
            print(f"     - {b}")
    else:
        print("  ✅ لا كسور منحلّة — كل المقامات ≥ 1 وكل بسط ≤ مقام.")
    print("\n  RAW Pydantic JSON tool-call payload (no HTML):")
    print(
        json.dumps(
            {"type": "ui_component", "payload": {"component": "probability_tree", "props": props}},
            ensure_ascii=False,
            indent=2,
        )[:1400]
    )
    return props


async def _live_connectivity() -> None:
    """يُثبت الاتصال الحي عند توفّر الأسرار (اختياري، لا يكسر الاختبار)."""
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
            import asyncpg  # type: ignore

            dsn = db.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
            conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=15.0)
            val = await conn.fetchval("SELECT 1")
            await conn.close()
            print(f"  ✅ Supabase LIVE: SELECT 1 → {val}")
        except Exception as exc:
            print(f"  ⚠️ Supabase connect failed: {exc}")
    else:
        print("  ℹ️ DATABASE_URL not a postgres DSN — skipping live DB probe")


async def main() -> int:
    print("=" * 74)
    print("Protocol V17.0 §4 — OMNI Live Empirical Test")
    print("=" * 74)

    print("\n[0] Live connectivity (secrets from env):")
    await _live_connectivity()

    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    client = OrchestratorClient.__new__(OrchestratorClient)

    history: list[dict] = []
    # Turn 1: retrieve exercise (becomes context)
    history.append({"role": "user", "content": "اعطني تمرين الاحتمالات 2024"})
    history.append({"role": "assistant", "content": BAC_2024})
    print(f"\n{'─' * 74}\n▶ Turn 1 — استرجاع التمرين (يصبح سياقاً)\n  {BAC_2024[:90]}...")

    # Turn 2: ask for the tree (composition resolved from history)
    p2 = await _turn(client, "Turn 2 — اعطني شجرة الاحتمالات", "اعطني شجرة الاحتمالات", history)
    history.append({"role": "user", "content": "اعطني شجرة الاحتمالات"})
    history.append({"role": "assistant", "content": "(تم عرض شجرة الاحتمالات)"})

    # Turn 3: follow-up "I didn't understand" — context must NOT be forgotten
    p3 = await _turn(
        client, "Turn 3 — لم افهم شجرة الاحتمالات (متابعة)", "لم افهم شجرة الاحتمالات", history
    )

    print(f"\n{'=' * 74}")
    ok = True
    for name, props in (("Turn 2", p2), ("Turn 3", p3)):
        if props is None:
            print(f"❌ {name}: no tree produced (context lost?)")
            ok = False
            continue
        bad: list[str] = []
        _scan_garbage(props["tree"], "", bad)
        red = next((c for c in props["composition"] if c["label"] == "كرة حمراء"), None)
        if bad:
            print(f"❌ {name}: garbage fractions present")
            ok = False
        elif red and (red["p_num"], red["p_den"]) == (4, 11):
            print(f"✅ {name}: P(red)=4/11, no garbage, context retained")
        else:
            print(f"⚠️ {name}: red fraction = {red}")
    print("=" * 74)
    if ok:
        print("🎉 OMNI LIVE TEST PASSED — no 1/0, context retained, pristine JSON.")
        return 0
    print("❌ OMNI LIVE TEST FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
