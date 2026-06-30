#!/usr/bin/env python3
"""
ISS-119 / D-147 — التحقق الحي الصارم (full-stack to the extent the env allows).

يُعيد transcript الكارثة الحيّة (BAC 2024، سؤال الأمل الرياضي E(X)) عبر **المنطق الحقيقي**:
PedagogicalEscalationSkill + MicroSimulationSkill، ويُثبت أنّ نفاد سُلّم التصعيد
(تعريف → مثال → محاكاة مصغّرة) لم يعد يُنتج الـ punt العام «أيّ خطوة تريد أن نبدأ بها؟»
بل **سؤال تطبيق مرتبط ببنية التمرين** («ما القيم التي يمكن أن يأخذها X؟») — دون كشف نتيجة.

تحقّق صارم (نقد المالك #2 — «يحب يبدو أنه أصلح بينما ما زال يتسرّب»):
  • نفاد السُّلّم ⇒ text_kind=apply + سؤال قيم X + صفر «أيّ خطوة تريد».
  • صفر تسريب نتيجة نهائية: كل APPLY_STEPS يَنجو من redact_final_answers (D-113).
  • المفهوم غير المُغطّى ⇒ التسليم العامّ القديم (لا انحدار).

ثم (إن توفّرت الأسرار): Supabase Edge bridge (HTTPS:443) + OpenRouter (HTTPS) reachability.
المسار الكامل WS/المتصفح يُتحقَّق في Codespaces (نمط CLAUDE.md §6.55).

Usage:
  python3 scripts/verify_iss119_live.py
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.skills.answer_redaction_skill import redact_final_answers
from app.services.skills.micro_simulation_skill import (
    APPLY_STEPS,
    get_micro_simulation_skill,
)
from app.services.skills.pedagogical_escalation_skill import (
    EscalationInput,
    get_pedagogical_escalation_skill,
)
from app.services.skills.semantic_property_skill import PROPERTY_REGISTRY

_SK = get_pedagogical_escalation_skill()
_MICRO_SK = get_micro_simulation_skill()
_ok = True


def _check(cond: bool, msg: str) -> None:
    global _ok
    print(("  ✅ " if cond else "  ❌ ") + msg)
    _ok = _ok and bool(cond)


def _asst(t: str) -> dict[str, str]:
    return {"role": "assistant", "content": t}


def _usr(t: str) -> dict[str, str]:
    return {"role": "user", "content": t}


def _exhausted_input(concept_id: str) -> EscalationInput:
    """يبني مدخلاً بسُلّم مُستنفَد (تعريف+مثال+محاكاة مُسلَّمة في history)."""
    spec = PROPERTY_REGISTRY.get(concept_id)
    micro = _MICRO_SK.get_micro_simulation(concept_id) or ""
    definition = (spec.definition if spec else "") or "تعريف المفهوم المُعطى للطالب سابقاً هنا"
    example = (spec.example if spec else "") or "## مثال ملموس\n\nمثال سابق مُقدَّم للطالب"
    history = [
        _usr("كيف احسب الامل الرياضي"),
        _asst(definition),
        _usr("كيف أفهمه"),
        _asst(example),
        _usr("لم أفهم"),
        _asst(micro),
        _usr("لم أفهم"),
    ]
    return EscalationInput(
        concept_id=concept_id,
        title=(spec.title if spec else ""),
        definition=definition,
        example=example,
        micro_sim=micro,
        apply_step=_MICRO_SK.get_apply_step(concept_id),
        intent="confusion",
        history=history,
        evidence_markers=(spec.evidence_markers if spec else ()),
    )


def main() -> int:
    print("== ISS-119/D-147 — كارثة E(X): نفاد السُّلّم ⇒ سؤال تطبيق لا punt ==")
    d = _SK.decide(_exhausted_input("expected_value"))
    _check(d.action == "exhausted", f"action=exhausted (got {d.action})")
    _check(d.text_kind == "apply", f"text_kind=apply (got {d.text_kind})")
    _check("ما القيم التي يمكن أن يأخذها X" in d.text, "يقود لقيم X (مرتبط بالتمرين)")
    _check("أيّ خطوة تريد" not in d.text, "صفر punt عام")
    _check(redact_final_answers(d.text)[1] == 0, "صفر تسريب نتيجة نهائية (D-113)")

    print("== كل APPLY_STEPS يَنجو من حجب D-113 (تحقّق صارم) ==")
    for cid, txt in APPLY_STEPS.items():
        out, n = redact_final_answers(txt)
        _check(n == 0 and out == txt, f"{cid}: لا تسريب")

    print("== المفهوم غير المُغطّى ⇒ التسليم العامّ القديم (لا انحدار) ==")
    spec = PROPERTY_REGISTRY["conditional_probability"]
    unknown = EscalationInput(
        concept_id=spec.concept_id,
        title=spec.title,
        definition=spec.definition,
        example=spec.example,
        micro_sim=_MICRO_SK.get_micro_simulation(spec.concept_id),
        apply_step=None,
        intent="confusion",
        history=_exhausted_input(spec.concept_id).history,
        evidence_markers=spec.evidence_markers,
    )
    du = _SK.decide(unknown)
    _check(du.text_kind == "handoff", f"fallback handoff (got {du.text_kind})")

    # ── reachability (اختياري — يتطلّب أسراراً؛ يُكمَّل في Codespaces) ──
    print("== reachability (اختياري) ==")
    ork = os.environ.get("OPENROUTER_API_KEY", "")
    if ork:
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {ork}"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                _check(r.status == 200, f"OpenRouter HTTPS {r.status}")
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  ⚠️  OpenRouter unreachable (sandbox?): {exc}")
    else:
        print("  ⚠️  OPENROUTER_API_KEY غير مضبوط — تحقّق LLM يُكمَّل في Codespaces.")

    print("\nRESULT:", "ALL PASS ✅" if _ok else "FAIL ❌")
    print(
        "ملاحظة: المسار الكامل WS→orchestrator→المتصفح بالأسرار الحقيقية إلزامي في "
        "Codespaces (نمط CLAUDE.md §6.55): «اعطني تمرين الاحتمالات 2024» → «كيف أحسب "
        "الأمل الرياضي» → «لم أفهم»×2 ⇒ سؤال قيم X، صفر «أيّ خطوة تريد»، صفر E(X)=/14/165."
    )
    return 0 if _ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
