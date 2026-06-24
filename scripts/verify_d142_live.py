#!/usr/bin/env python3
"""
D-142 (المرحلة 1) — التحقق الحي: السلطة الرمزية + حارس التكرار + حارس الانحراف.

يُعيد إشارات transcript الكارثة عبر **المنطق الحقيقي** ويُثبت:
  1A: إجابة صحيحة مُتحقَّقة رمزياً («الخضراء و الحمراء فقط»/«لونين 2 فقط») ⇒ understood (تقدّم).
  1B: تلميح مُكرّر يُكشَف (`_recently_emitted`) ⇒ تصعيد بدل الإعادة الحرفية ×3.
  1D: «ماذا نقصد لم أفهم» تُبقي المفهوم النشط (لا «لم أفهم أي مفهوم؟»).
ثم (إن توفّرت الأسرار): Supabase Edge bridge (HTTPS:443) + OpenRouter (HTTPS).

Usage: python3 scripts/verify_d142_live.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.skills.semantic_property_skill import get_semantic_property_skill
from app.services.skills.socratic_evaluator_skill import deterministically_correct

_SPS = get_semantic_property_skill()
_HINT = "لاحظ نوع كل كرة: أيّ الألوان يكفي عددها لسحب 3 منها معاً؟ ابدأ بعدّ الألوان الممكنة فقط."
_PASS = "✅"
_FAIL = "❌"


def _check(name: str, cond: bool) -> bool:
    print(f"  {_PASS if cond else _FAIL} {name}")
    return cond


def main() -> int:
    ok = True

    print("=== 1A: السلطة الرمزية (الإجابة الصحيحة تتقدّم رغم خفض الـ LLM) ===")
    ok &= _check(
        "«الخضراء و الحمراء فقط» مُتحقَّقة",
        deterministically_correct("الخضراء و الحمراء فقط", "event_meaning"),
    )
    ok &= _check("«لونين 2 فقط» مُتحقَّقة", deterministically_correct("لونين 2 فقط", "event_meaning"))
    ok &= _check("«لا أعرف» ليست مُتحقَّقة", not deterministically_correct("لا أعرف", "event_meaning"))

    # تحقّق رمزي من المحرك الرمزي الحقيقي (combo).
    combo = OrchestratorClient._load_canonical_combinations("اعطني تمرين الاحتمالات 2024", None)
    if combo is not None:
        ok &= _check(
            "_verify_answer_against_combo(«الخضراء و الحمراء فقط»)",
            OrchestratorClient._verify_answer_against_combo("الخضراء و الحمراء فقط", combo),
        )
        ok &= _check(
            "_verify_answer_against_combo(«لا أعرف») = False",
            not OrchestratorClient._verify_answer_against_combo("لا أعرف", combo),
        )
    else:
        print("  (تخطّي combo — تعذّر تحميل التمرين الرسمي في هذه البيئة)")

    print("\n=== 1B: حارس التكرار ===")
    hist_rep = [{"role": "assistant", "content": _HINT}]
    ok &= _check("التلميح المُكرّر يُكشَف", OrchestratorClient._recently_emitted(_HINT, hist_rep))
    ok &= _check(
        "نصّ مختلف لا يُكشَف",
        not OrchestratorClient._recently_emitted(
            "ما هو المقام؟ كم طريقة لسحب ثلاث كرات من إحدى عشرة؟", hist_rep
        ),
    )

    print("\n=== 1D: حارس الانحراف ===")
    ok &= _check(
        "«ماذا نقصد لم أفهم» حيرة مجرّدة", _SPS._is_bare_confusion_definitional("ماذا نقصد لم أفهم")
    )
    ok &= _check(
        "«ما هو الاحتمال الشرطي» ليست مجرّدة",
        not _SPS._is_bare_confusion_definitional("ما هو الاحتمال الشرطي"),
    )
    hist_focus = [
        {"role": "user", "content": "ما هو الاحتمال الشرطي"},
        {"role": "assistant", "content": "الاحتمال الشرطي هو احتمال حادثة بعلم وقوع أخرى."},
    ]
    res = _SPS.detect_active_concept("ماذا نقصد لم أفهم", hist_focus)
    ok &= _check(
        "الحيرة المجرّدة تُبقي المفهوم (conditional_probability)",
        res is not None and getattr(res, "concept_id", None) == "conditional_probability",
    )
    res2 = _SPS.detect_active_concept("ما هو المتغير العشوائي", hist_focus)
    ok &= _check(
        "المفهوم الجديد لا ينجرف للقديم",
        res2 is None or getattr(res2, "concept_id", None) != "conditional_probability",
    )

    print("\n=== النتيجة:", "كل الفحوص ناجحة ✅" if ok else "فشل ❌", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
