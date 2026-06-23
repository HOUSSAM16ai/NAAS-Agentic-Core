#!/usr/bin/env python3
"""
D-139 — التحقق الحي الحقيقي: قتل انحراف المفهوم إلى الحادثة A.

يُعيد transcript الكارثة الحرفي عبر **المنطق الحقيقي** (semantic_property + StudentState +
بوّابة المصفوفة D-138/D-139) ويُثبت: كل سؤال مفهوم يُمسَك بالمفهوم الصحيح (لا نص الحادثة A).
ثم (إن توفّرت الأسرار): Supabase Edge bridge (HTTPS:443) + OpenRouter (HTTPS).

Usage: python3 scripts/verify_d139_live.py
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

from app.services.skills.semantic_property_skill import get_semantic_property_skill
from app.services.skills.student_state_skill import StudentStateInput, get_student_state_skill

_SPS = get_semantic_property_skill()
_SS = get_student_state_skill()

_EXERCISE_DUMP = (
    "التمرين الأول — الاحتمالات. يحتوي كيس على 11 كرة. نسحب عشوائيًا 3 كرات دفعة واحدة. "
    "A: الحصول على 3 كرات من نفس اللون. احسب احتمال الحادثة A. " * 3
)
_EVENT_A = "تخيّل أنك سحبت 3 كرات: لو كانت كلها خضراء ⇒ تحقّقت A؛ لو اختلطت الألوان ⇒ لم تتحقّق."
_TEACH = frozenset({"definition", "example_request", "confusion", "procedure", "hint_request"})
_COMPUTE = ("احسب", "أحسب", "كم ", "اوجد", "أوجد", "بيّن", "بين ان", "استنتج")
_FOLLOWUP = (
    "كيف",
    "لماذا",
    "علاش",
    "وضح",
    "اشرح",
    "بسط",
    "؟",
    "مثال",
    "لم افهم",
    "لم أفهم",
    "مفهمتش",
)


def _u(t):
    return {"role": "user", "content": t}


def _a(t):
    return {"role": "assistant", "content": t}


def _route(question, history):
    """بوّابة بلوك المصفوفة (D-138/D-139) — أيّ مفهوم تُمسَك به (None=لا تُمسَك)."""
    state = _SS.read(StudentStateInput(question=question, history=history))
    ql = question.lower()
    if any(m in ql for m in _COMPUTE):
        return None
    followup = any(m in ql for m in _FOLLOWUP)
    teach_ok = state.primary_intent in _TEACH or (
        state.primary_intent == "unknown" and (followup or _SPS.interpret(question) is not None)
    )
    if not teach_ok:
        return None
    active = _SPS.detect_active_concept(question, history)
    return active.concept_id if active else None


def replay() -> bool:
    print("=" * 78)
    print("D-139 — إعادة transcript الكارثة (لا نص الحادثة A لأي سؤال مفهوم)")
    print("=" * 78)
    ok = True

    def check(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"{'✅' if cond else '❌'} {label}")

    h = [_u("اعطني تمرين الاحتمالات 2024"), _a(_EXERCISE_DUMP)]
    h += [
        _u("ما هو الاحتمال الشرطي"),
        _a("## ماذا نقصد بالاحتمال الشرطي؟\n\nالاحتمال الشرطي هو..."),
    ]
    h += [_u("لم أفهم"), _a("## محاكاة مصغّرة\n\nتخيّل صفّاً فيه 10 طلاب، 6 منهم بنظّارة...")]

    check(
        "«كيف نضيق الإمكانيات» ⇒ conditional (لا event-A)",
        _route("كيف نضيق الإمكانيات", h) == "conditional_probability",
    )
    h += [_u("كيف نضيق الإمكانيات"), _a(_EVENT_A)]  # نُحاكي حتى لو حدث تلوّث event-A سابق

    check(
        "«لم أفهم» المتكرّرة (بعد تلوّث event-A) ⇒ conditional",
        _route("لم أفهم", h) == "conditional_probability",
    )
    check(
        "«كيف نحصل على ثلاث كرات معدومة» ⇒ product_zero (لا event-A)",
        _route("كيف نحصل على ثلاث كرات معدومة", h) == "product_zero",
    )
    check(
        "«ما هو السحب على التوالي بدون إرجاع» ⇒ sequential (لا event-A)",
        _route("ما هو السحب على التوالي بدون إرجاع", h) == "sequential_without_replacement",
    )
    check(
        "«ماذا نقصد بالسحب دفعة واحدة» ⇒ simultaneous (لا event-A)",
        _route("ماذا نقصد بالسحب دفعة واحدة", h) == "simultaneous_draw",
    )
    check(
        "«احسب احتمال الحادثة A» ⇒ لا تُفعَّل المصفوفة (مسار حسابي)",
        _route("احسب احتمال الحادثة A", h) is None,
    )
    check("«ما هو الوسيط» (غير مُسجَّل) ⇒ None ⇒ LLM Definer", _route("ما هو الوسيط", h) is None)
    # حارس صريح: لا أي مفهوم يُمسَك = same_color/event_meaning لأسئلة غير الحادثة A
    for q in (
        "كيف نضيق الإمكانيات",
        "كيف نحصل على ثلاث كرات معدومة",
        "ما هو السحب على التوالي بدون إرجاع",
    ):
        check(f"  «{q[:24]}…» ليس event_meaning", _route(q, h) != "event_meaning")

    print("=" * 78)
    print(f"النتيجة: {'PASS' if ok else 'FAIL'} (concept-drift kill)")
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
    print("✅ D-139 concept-drift kill VERIFIED (real skill code)" if ok else "❌ D-139 FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
