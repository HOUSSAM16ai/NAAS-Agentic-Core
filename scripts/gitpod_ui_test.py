#!/usr/bin/env python3
"""
Protocol V14.0 §4 — Gitpod Live Empirical Test (Generative UI Pipeline).

يُثبت أن الخلفية تحسب احتمالات حقيقية ديناميكياً من نص بكالوريا 2024 العربي،
لا قيماً مُبرمَجة مسبقاً. يُحاكي تمرين الاحتمالات (كيس فيه 11 كرة) ويطبع حمولة
JSON الخام لاستدعاء الأداة (ui_component) عبر المسار الإنتاجي الكامل
(``OrchestratorClient._build_probability_tree_props``).

التشغيل:
    python scripts/gitpod_ui_test.py

البيئة (للمسار الكامل عبر orchestrator):
    DATABASE_URL=... SECRET_KEY=... ENVIRONMENT=testing ... python scripts/gitpod_ui_test.py

إن أردت إثراء التسميات حيّاً عبر OpenRouter (اختياري) صدّر OPENROUTER_API_KEY.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# بيئة افتراضية آمنة (sqlite + mock) إن لم تُضبط — حتى يعمل السكربت محلياً.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-pipeline-secure-length")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LLM_MOCK_MODE", "1")
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_ROLE_KEY", "dummy")

# نص بكالوريا 2024 (مقتبس من knowledge_base/bac2024_*): كيس فيه 11 كرة.
BAC_2024_PROBABILITY = (
    "يحتوي كيس على 11 كرة متماثلة لا تُفرّق باللمس موزعة كما يلي: "
    "كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. "
    "نسحب عشوائياً 3 كرات على التوالي وبدون إرجاع. "
    "ارسم شجرة الاحتمالات واحسب احتمال سحب كرة حمراء."
)


def _assert_dynamic(props: dict) -> None:
    """يتحقق أن الكسور محسوبة ديناميكياً (4/11) لا قيمة 0.5 وهمية."""
    comp = props.get("composition") or []
    red = next((c for c in comp if c.get("label") == "كرة حمراء"), None)
    assert red is not None, "لم يُستخرَج كيان 'كرة حمراء' من النص العربي"
    assert (red["p_num"], red["p_den"]) == (4, 11), (
        f"P(حمراء) يجب أن يكون 4/11 محسوباً ديناميكياً، وجدنا {red['p_num']}/{red['p_den']}"
    )
    assert props.get("is_illustrative") is False, "القيم محسوبة لا توضيحية"
    assert props.get("calculated") is True, "العلم calculated يجب أن يكون True"
    # برهان «لا 0.5 غبية»: لا عقدة من المستوى الأول مقامها 2 افتراضياً
    for c in comp:
        assert not (c["p_num"] == 1 and c["p_den"] == 2), "كُشِفت قيمة 0.5 وهمية!"


async def _via_orchestrator() -> dict | None:
    """يستدعي المسار الإنتاجي الكامل إن أمكن استيراد OrchestratorClient."""
    try:
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient
    except Exception as exc:  # pragma: no cover
        print(f"ℹ️ تعذّر استيراد OrchestratorClient ({exc}); أستخدم الـ Skill مباشرة.")
        return None
    client = OrchestratorClient.__new__(OrchestratorClient)
    return await client._build_probability_tree_props(BAC_2024_PROBABILITY)


def _via_skill() -> dict | None:
    """مسار احتياطي مباشر عبر الـ Skill (يكفي لإثبات الحساب الديناميكي)."""
    from app.services.skills.probability_skill import (
        ProbabilityCalculatorSkill,
        ProbabilityModelOutput,
    )

    out = ProbabilityCalculatorSkill().analyze(BAC_2024_PROBABILITY)
    if not isinstance(out, ProbabilityModelOutput):
        return None
    return {
        "title": out.title,
        "is_illustrative": False,
        "calculated": True,
        "with_replacement": out.with_replacement,
        "total": out.total,
        "strategy": out.strategy,
        "composition": [c.model_dump() for c in out.composition],
        "tree": out.tree,
    }


def main() -> int:
    print("=" * 78)
    print("Protocol V14.0 §4 — Gitpod Live Empirical Test: Generative UI Pipeline")
    print("=" * 78)
    print(f"\nنص المسألة (بكالوريا 2024):\n{BAC_2024_PROBABILITY}\n")

    props = asyncio.run(_via_orchestrator())
    path = "OrchestratorClient._build_probability_tree_props (full production path)"
    if props is None:
        props = _via_skill()
        path = "ProbabilityCalculatorSkill.analyze (direct skill path)"

    if props is None:
        print("❌ FAILED — لم يُنتَج أي نموذج احتمالي.")
        return 1

    print(f"المسار المستخدَم: {path}\n")
    print("RAW JSON tool-call payload (ui_component → probability_tree):")
    tool_call = {
        "type": "ui_component",
        "payload": {
            "component": "probability_tree",
            "props": props,
            "fallback_text": "شجرة الاحتمالات (نص بديل عند تعذّر التصيير).",
        },
    }
    print(json.dumps(tool_call, ensure_ascii=False, indent=2))

    print("\n— تحقّق الحساب الديناميكي —")
    try:
        _assert_dynamic(props)
    except AssertionError as e:
        print(f"❌ {e}")
        return 1
    for c in props["composition"]:
        print(f"   • P({c['label']}) = {c['p_num']}/{c['p_den']}  ≈ {c['p_decimal']}")
    print("\n✅ PROVEN — الاحتمالات كسور محسوبة ديناميكياً من النص العربي (P(حمراء)=4/11)،")
    print("   لا قيمة 0.5 مُبرمَجة مسبقاً. الخلفية تُخرج JSON منظَّماً فقط (لا HTML).")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
