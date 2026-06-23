#!/usr/bin/env python3
"""
D-138 — التحقق الحي الحقيقي (full-stack to the extent the env allows).

يُعيد transcript الكارثة (الاحتمال الشرطي) عبر **المنطق الحقيقي للمصفوفة التصعيدية** —
PedagogicalEscalationSkill + MicroSimulationSkill + SemanticPropertySkill — ويُثبت:
  تعريف → مثال → محاكاة مصغّرة؛ «اعطني مثال عددي» ⇒ L3؛ «لم أفهم» ⇒ تصعيد لا تكرار؛ استنفاد ⇒
  تسليم؛ المعايرة بالقدرة؛ Understanding-Signal ⇒ توقّف؛ Misconception ⇒ تدخّل مُوجَّه.

ثم (إن توفّرت الأسرار): Supabase Edge bridge (HTTPS:443) + OpenRouter (HTTPS).
المسار الكامل WS/المتصفح يُتحقَّق في Codespaces (نمط CLAUDE.md §6.55).

Usage:
  python3 scripts/verify_d138_live.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.skills.answer_redaction_skill import redact_final_answers
from app.services.skills.micro_simulation_skill import (
    MICRO_SIM_MAX_CHARS,
    MICRO_SIMULATIONS,
    get_micro_simulation_skill,
)
from app.services.skills.pedagogical_escalation_skill import (
    L1_DEFINITION,
    L2_ANALOGY,
    L3_MICRO_SIMULATION,
    EscalationInput,
    get_pedagogical_escalation_skill,
)
from app.services.skills.semantic_property_skill import PROPERTY_REGISTRY

_SPEC = PROPERTY_REGISTRY["conditional_probability"]
_MICRO = get_micro_simulation_skill().get_micro_simulation(_SPEC.concept_id)
_SK = get_pedagogical_escalation_skill()


def _inp(intent, history, sup=None, mis=None, mtype=None):
    return EscalationInput(
        concept_id=_SPEC.concept_id,
        title=_SPEC.title,
        definition=_SPEC.definition,
        example=_SPEC.example,
        micro_sim=_MICRO,
        intent=intent,
        history=history,
        support_level=sup,
        evidence_markers=_SPEC.evidence_markers,
        misconception_intervention=mis,
        misconception_mtype=mtype,
    )


def _u(t):
    return {"role": "user", "content": t}


def _a(t):
    return {"role": "assistant", "content": t}


def replay() -> bool:
    print("=" * 78)
    print("D-138 — إعادة transcript الكارثة عبر المصفوفة التصعيدية الحقيقية")
    print("=" * 78)
    ok = True
    h: list[dict] = []

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"{'✅' if cond else '❌'} {label}")

    d = _SK.decide(_inp("definition", h))
    check(
        f"T1 «ما هو الاحتمال الشرطي» → L{d.strategy_level} ({d.action})",
        d.strategy_level == L1_DEFINITION,
    )
    h += [_u("ما هو الاحتمال الشرطي"), _a(d.text)]

    d = _SK.decide(_inp("example_request", h))
    check(f"T2 «اعطني مثال» → L{d.strategy_level}", d.strategy_level == L2_ANALOGY)
    h += [_u("اعطني مثال"), _a(d.text)]

    d = _SK.decide(_inp("example_request", [*h, _u("اعطني مثال عددي")]))
    check(
        f"T3 «اعطني مثال عددي» → L{d.strategy_level} محاكاة={'محاكاة' in d.text}",
        d.strategy_level == L3_MICRO_SIMULATION
        and "10 طلاب" in d.text
        and "كلها خضراء" not in d.text,
    )
    h += [_u("اعطني مثال عددي"), _a(d.text)]

    d = _SK.decide(_inp("confusion", h))
    check(
        f"T4 «لم أفهم» → {d.action} (لا تكرار، لا event-A)",
        d.action == "exhausted" and "كلها خضراء" not in d.text,
    )
    h += [_u("لم أفهم"), _a(d.text)]

    d = _SK.decide(_inp("procedure", h))
    check(f"T5 «كيف» → {d.action}", d.action == "exhausted")

    # تصعيد على الحيرة (مسار منفصل)
    h2 = [_u("ما هو"), _a(_SK.decide(_inp("definition", [])).text)]
    h2 += [_u("اعطني مثال"), _a(_SK.decide(_inp("example_request", h2)).text)]
    d = _SK.decide(_inp("confusion", h2))
    check("«لم أفهم» بعد L1+L2 → L3 (تصعيد لا تكرار)", d.strategy_level == L3_MICRO_SIMULATION)

    # المعايرة بالقدرة
    low = _SK.decide(_inp("confusion", h2, sup=2)).strategy_level
    high = _SK.decide(
        _inp("confusion", [_u("ما هو"), _a(_SK.decide(_inp("definition", [])).text)], sup=5)
    ).strategy_level
    check(f"المعايرة: منخفضة(sup=2)→L{low} ≥ عالية(sup=5)→L{high}", low >= high)

    # Understanding Signal
    d = _SK.decide(_inp("confusion", [_u("اها فهمت، تقلص الفضاء فنقسم على عدد اقل")]))
    check(f"Understanding Signal → {d.action}", d.action == "mastered")

    # Misconception
    d = _SK.decide(
        _inp(
            "confusion",
            [_u("نضرب الاحتمالين؟")],
            mis="الاحتمال الشرطي ليس ضرب احتمالين",
            mtype="rule_property",
        )
    )
    check(
        f"Misconception → {d.action}",
        d.action == "target_misconception" and "ليس ضرب احتمالين" in d.text,
    )

    # Micro-sim: حتمي، قصير، يَنجو من D-113
    longest = max(len(s) for s in MICRO_SIMULATIONS.values())
    leak = any("14/165" in s or "14 من 165" in s for s in MICRO_SIMULATIONS.values())
    survives = all(
        redact_final_answers(s, support_level=5)[0].strip() for s in MICRO_SIMULATIONS.values()
    )
    check(
        f"Micro-sim: أطول={longest}≤{MICRO_SIM_MAX_CHARS}، لا تسريب={not leak}، يَنجو D-113={survives}",
        longest <= MICRO_SIM_MAX_CHARS and not leak and survives,
    )

    print("=" * 78)
    print(f"النتيجة: {'PASS' if ok else 'FAIL'} (escalation matrix)")
    print("=" * 78)
    return ok


def check_supabase_bridge() -> None:
    url = os.environ.get("SUPABASE_EDGE_FUNCTION_URL", "").strip()
    key = os.environ.get("SUPABASE_EDGE_FUNCTION_KEY", "").strip()
    if not url or not key:
        print("ℹ️  Supabase bridge: secrets غير محقونة — تخطّي (يُتحقَّق في Codespaces).")
        return
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"sql_query": "SELECT count(*) AS n FROM customer_messages;"}).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        rows = body.get("data") or []
        print(f"✅ Supabase bridge حيّ: customer_messages = {rows[0].get('n') if rows else '?'}")
    except (urllib.error.URLError, ValueError, KeyError) as exc:  # pragma: no cover
        print(f"⚠️  Supabase bridge تعذّر ({exc}) — يُتحقَّق في Codespaces.")


def check_openrouter() -> None:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print("ℹ️  OpenRouter: المفتاح غير محقون — تخطّي (يُتحقَّق في Codespaces).")
        return
    try:
        payload = {
            "model": "openai/gpt-oss-120b:free",
            "messages": [{"role": "user", "content": "قل: جاهز"}],
            "max_tokens": 8,
        }
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode())
        print(f"✅ OpenRouter حيّ: finish_reason={body['choices'][0].get('finish_reason')}")
    except (urllib.error.URLError, ValueError, KeyError) as exc:  # pragma: no cover
        print(f"⚠️  OpenRouter تعذّر ({exc}) — يُتحقَّق في Codespaces.")


def main() -> int:
    ok = replay()
    print()
    check_supabase_bridge()
    check_openrouter()
    print()
    print("✅ D-138 escalation matrix VERIFIED (real skill code)" if ok else "❌ D-138 FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
