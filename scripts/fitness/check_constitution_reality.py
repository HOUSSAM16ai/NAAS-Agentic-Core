#!/usr/bin/env python3
"""يفرض أن الدستور **يساوي** الواقع — ولا يناقض نفسه (D-192).

**لماذا هذه البوّابة موجودة:**

بوّابة D-188 (``check_memory_coherence``) أوقفت انحراف **الفهرس والترتيب والحجم**.
لكنها لا ترى صنفاً أخطر: **رقماً مكتوباً باليد في النثر**. وقد وجدنا في 2026-07-31 أن
``CLAUDE.md`` يناقض **نفسه** في موضعين، وأن كلا الرقمين خاطئ:

* §0.5 يقول «٢٤ مهارة اليوم» بينما §0.7 يقول «Skills Engine (27 skills)» — والواقع
  **36** مهارة مُسجَّلة في ``app/services/skills/registry.py``.
* §3 وD-185 يقولان «API-first **13/13**» بينما §6.7.ط يقول «**11/11** حقيقي» —
  والواقع **13** عقد خدمة مُلتزَم في ``docs/contracts/openapi/``.

الجذر واحد: **رقمٌ يُكتب يدوياً في نثرٍ لا يعرف مصدره**. كل تغييرٍ في الكود يجعله
أقدم، ولا شيء يلاحظ. الدواء ليس «تصحيح الرقم» — فسيتقادم غداً — بل **اشتقاقه**:
الرقم يُحسَب من المصدر، والنثر يحمل مؤشراً لا قيمة.

**ما تفرضه:**

1. **الأرقام مشتقّة**: أيّ عددٍ للمهارات/العقود في الدستور يجب أن يطابق المُشتقّ.
2. **لا تناقض ذاتي**: الكمّية نفسها لا تظهر بقيمتين في قسمين.
3. **ادّعاءات الرموز صحيحة**: كل قاعدة تسمّي رمزاً في الكود تُختبَر على المصدر —
   فلا تعود «القاعدة المعلنة بنصفها» (``math_explanation_card`` كانت مُسجَّلة في
   الواجهة وغائبة عن عقد الخادم، فلا تصل الطالب أبداً).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
OPENAPI_DIR = REPO_ROOT / "docs/contracts/openapi"

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _skill_count() -> int:
    """يشتقّ عدد المهارات المُسجَّلة من سجلّ المهارات نفسه (بلا استيراد التطبيق).

    نقرأ استدعاءات ``register(...)`` نصّياً: استيراد ``app`` يتطلّب إعدادات وقاعدة
    بيانات، والبوّابات يجب أن تعمل في sandbox مُتدهور (نفس قيد ``db_bridge``).
    """
    registry = (REPO_ROOT / "app/services/skills/registry.py").read_text(encoding="utf-8")
    return len(set(re.findall(r'name=["\']([a-z0-9_]+)["\']', registry)))


def _contract_count() -> int:
    """عدد عقود الخدمات المُلتزَمة — المصدر: الملفّات على القرص."""
    return len(sorted(OPENAPI_DIR.glob("*-openapi.json")))


def _claims(text: str, pattern: str) -> list[tuple[int, str]]:
    """يُعيد (رقم السطر، القيمة) لكل مطابقة — لتقارير تُشير إلى الموضع."""
    out: list[tuple[int, str]] = []
    for match in re.finditer(pattern, text):
        line_no = text[: match.start()].count("\n") + 1
        out.append((line_no, match.group(1)))
    return out


def _check_no_self_contradiction(text: str) -> list[str]:
    """القاعدة 2: الكمّية نفسها لا تظهر بقيمتين مختلفتين في الدستور."""
    errors: list[str] = []

    # (أ) نسبة API-first «N/N».
    ratios = {value for _, value in _claims(text, r"API-first\s+\*{0,2}(\d+)/\d+")}
    if len(ratios) > 1:
        errors.append(
            f"❌ CLAUDE.md يناقض نفسه في نسبة API-first: {sorted(ratios)}.\n"
            f"   كمّيةٌ واحدة بقيمتين — استبدل الأرقام بمؤشرٍ إلى المصدر المُشتقّ."
        )

    # (ب) عدد المهارات (عربي أو إنجليزي).
    skill_claims = {
        value.translate(_AR_DIGITS)
        for _, value in _claims(text, r"\(?([0-9٠-٩]{1,3})\s*(?:مهارة|skills)")
    }
    if len(skill_claims) > 1:
        errors.append(
            f"❌ CLAUDE.md يناقض نفسه في عدد المهارات: {sorted(skill_claims)}.\n"
            f"   كمّيةٌ واحدة بقيمتين — العدد يُشتَقّ من `registry.py` لا يُكتب يدوياً."
        )
    return errors


def _check_derived_numbers(text: str) -> list[str]:
    """القاعدة 1: أيّ رقم مذكور يجب أن يطابق المُشتقّ من الكود."""
    errors: list[str] = []
    real_contracts = _contract_count()
    for line_no, value in _claims(text, r"API-first\s+\*{0,2}(\d+)/\d+"):
        if int(value) != real_contracts:
            errors.append(
                f"❌ CLAUDE.md:{line_no}: API-first {value}/… بينما المُشتقّ "
                f"{real_contracts} عقداً في docs/contracts/openapi/."
            )
    real_skills = _skill_count()
    for line_no, value in _claims(text, r"\(?([0-9٠-٩]{1,3})\s*(?:مهارة|skills)"):
        if int(value.translate(_AR_DIGITS)) != real_skills:
            errors.append(
                f"❌ CLAUDE.md:{line_no}: «{value} مهارة» بينما المُسجَّل فعلياً "
                f"{real_skills} مهارة في app/services/skills/registry.py."
            )
    return errors


#: ادّعاءات الرموز: (وصف، ملف، نصّ يجب أن يوجد). كل واحدة قاعدةٌ في الدستور
#: كان يمكن أن تُكتب وتبقى كاذبة — والاختبار يجعلها صادقةً بالبناء.
_SYMBOL_CLAIMS: tuple[tuple[str, str, str], ...] = (
    (
        "D-080: math_explanation_card قابلة للتسليم من الخادم لا من الواجهة وحدها",
        "app/contracts/streaming.py",
        '"math_explanation_card"',
    ),
    (
        "D-097: مُقطِّع نثر LLM يبقى مُعطَّلاً دائماً",
        "app/api/routers/customer_chat_support/frames.py",
        "return None",
    ),
    (
        "D-191: الكيانات المهيكلة نوعٌ حقيقي له قارئ حيّ",
        "app/services/skills/probability_models.py",
        "class ParsedEntities",
    ),
    (
        "D-191: التمرين قيد النقاش له مُحلٌّ واحد",
        "app/services/skills/exercise_context.py",
        "CANONICAL_EXERCISE_QUERY",
    ),
    (
        "D-116: كل مكوّنات الاحتمالات تُنهي المسار (يَعلو على شرط D-085)",
        "app/infrastructure/clients/orchestrator/probability_ui.py",
        '"terminate_pipeline": True',
    ),
)


def _check_symbol_claims() -> list[str]:
    errors: list[str] = []
    for description, rel, needle in _SYMBOL_CLAIMS:
        path = REPO_ROOT / rel
        if not path.is_file():
            errors.append(f"❌ {description}\n   الملفّ مفقود: {rel}")
            continue
        if needle not in path.read_text(encoding="utf-8"):
            errors.append(
                f"❌ ادّعاء دستوري لم يعد صحيحاً: {description}\n"
                f"   لم أجد {needle!r} في {rel}. صحّح الكود أو صحّح الدستور — "
                f"لا تتركهما متناقضين."
            )
    return errors


def main() -> int:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    errors = (
        _check_no_self_contradiction(text) + _check_derived_numbers(text) + _check_symbol_claims()
    )
    if errors:
        print("\n".join(errors))
        print(
            "\n📌 D-192: الدستور عقدٌ يساوي الواقع. الرقم يُشتَقّ ولا يُكتب يدوياً،\n"
            "   والكمّية الواحدة لا تحمل قيمتين، وكل رمزٍ يُذكَر يُختبَر على المصدر."
        )
        return 1
    print(
        f"✅ constitution = reality: بلا تناقض ذاتي · الأرقام مشتقّة "
        f"({_skill_count()} مهارة · {_contract_count()} عقداً) · "
        f"{len(_SYMBOL_CLAIMS)} ادّعاءات رموز مُتحقَّقة."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
