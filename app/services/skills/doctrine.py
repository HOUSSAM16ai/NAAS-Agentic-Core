"""
Skills Doctrine — Single Source of Truth لقواعد كل Skill في المشروع.

CLAUDE.md §0.5: «كل قدرة AI في النظام يجب أن تكون Skill — وحدة مستقلة قابلة
للقياس والاختبار والاستبدال». هذا الملف هو المرجع المركزي لكل قواعد التشغيل
التي يجب أن تحترمها الـ Skills.

**لماذا doctrine module مستقل؟**

قبل (Prompt Spaghetti):
    - قواعد الشرح متناثرة بين system prompts و LLM instructions
    - تغيير قاعدة = تعديل عشرات الـ prompts يدوياً
    - لا يوجد invariant CI gate يضمن أن الـ doctrine لم تنحرف

بعد (Skills Doctrine Module):
    - كل قاعدة تعيش كثابت Python (`tuple[str, ...]` أو `dict[str, str]`)
    - versioning صريح: تغيير قاعدة = bump version + update CI gate
    - اختبارات unit تثبت أن كل caller يحترم الـ doctrine الحية
    - CI gate يحرس على عدم drift بين الـ doctrine في الـ Skill والـ system prompt

**كيف يستخدم Skill قاعدة؟**

```python
from app.services.skills.doctrine import (
    RETRIEVAL_DOCTRINE,
    EXPLANATION_DOCTRINE,
    MODEL_ANSWER_RELIANCE_RULES,
)

# في Skill:
class BACExerciseSkill:
    def _build_explanation_prompt(self, full_content: str) -> str:
        return (
            "أنت أستاذ بكالوريا جزائر. اشرح وفقاً للقواعد التالية:\\n"
            + "\\n".join(f"- {r}" for r in EXPLANATION_DOCTRINE)
            + f"\\n\\nالتمرين + الإجابة النموذجية:\\n{full_content}"
        )
```

**كيف يضمن CI أن الـ doctrine متّسقة؟**

`scripts/fitness/check_skills_doctrine.py` يفحص:
1. كل Skill في `app/services/skills/` يستورد على الأقل قاعدة doctrine واحدة.
2. أي تعديل على قاعدة doctrine يجب أن يرافقه bump في الـ version.
3. الـ system prompts في `local_graph.py` تحتوي تمثيلاً قابلاً للتحقق من
   `EXPLANATION_DOCTRINE` (drift detection).

التاريخ:
    2026-05-18 (ISS-080 / D-068): إنشاء الـ doctrine module — استخراج
    EXPLANATION_DOCTRINE من `bac_exercise_skill.py`.

    2026-05-18 (ISS-CI-GREEN-001 / D-069): إضافة RETRIEVAL_DOCTRINE،
    MODEL_ANSWER_RELIANCE_RULES، CONTENT_INVOCATION_RULES، DETAILED_EXPLANATION_RULES
    كقواعد رسمية مستقلة، تطبيقاً لطلب المستخدم بتطوير منظومة الـ skills.
"""

from __future__ import annotations

from typing import Final

# ─────────────────────────────────────────────────────────────────────────────
# Doctrine Version Pinning
# ─────────────────────────────────────────────────────────────────────────────
#
# عند تعديل أي قاعدة من الـ doctrines أدناه:
#   1. حدّث الـ version (`MAJOR.MINOR.PATCH`).
#   2. شغّل `python scripts/fitness/check_skills_doctrine.py` ليُجدد الـ
#      doctrine hash في الـ lock file.
#   3. أضف entry في `.memory/decisions.md` يشرح *لماذا* تغيّرت.

#: نسخة doctrine استدعاء/استرجاع المحتوى — تُستخدم لـ drift detection في CI.
RETRIEVAL_DOCTRINE_VERSION: Final[str] = "1.0.0"

#: نسخة doctrine الشرح — تطابق `EXPLANATION_DOCTRINE_VERSION` في
#: `bac_exercise_skill.py` (يبقى متزامناً عبر تعريف موحَّد هنا).
EXPLANATION_DOCTRINE_VERSION: Final[str] = "2.0.0"

#: نسخة doctrine الاعتماد على الإجابة النموذجية.
MODEL_ANSWER_RELIANCE_VERSION: Final[str] = "1.0.0"

#: نسخة doctrine الشرح التفصيلي.
DETAILED_EXPLANATION_VERSION: Final[str] = "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# Content Invocation / Retrieval Doctrine
# ─────────────────────────────────────────────────────────────────────────────
# هذه القواعد تحكم *كيف يجب أن يُستدعى المحتوى التعليمي* من قاعدة المعرفة.
# المُستفيدون: `BACExerciseSkill._retrieve`, `_stream_local_retrieval_response`,
# `exercise_retrieval.detect_exercise_retrieval`.
# ─────────────────────────────────────────────────────────────────────────────

RETRIEVAL_DOCTRINE: Final[tuple[str, ...]] = (
    "Indexed-first retrieval: قَبل البحث الواسع، حاول مطابقة الفهرس المحدد "
    "(year + session + subject + exercise_number) في `knowledge_index`.",
    "Atomic file load: عند توفر `matched_entry`، حمِّل ملفاً واحداً بالضبط. "
    "لا scan على `knowledge_base/` يقرأ ملفات أخرى.",
    "Display strip: المُخرَج للمستخدم يجب أن يخلو من YAML frontmatter، "
    "أي قسم بعنوان «عناصر الإجابة» / «الإجابة النموذجية» / «الحل» / "
    "«Solutions» / «وسوم البحث»، أو أي علامات chunk الداخلية مثل `[ex:`، "
    "`[sol:`، `[grading:`.",
    "Streaming chunk integrity: التقسيم يجب أن يحافظ على سلامة LaTeX. "
    "أي `$...$` أو `$$...$$` أو `\\(...\\)` يُكشف ذرّياً.",
    "Pre-empt orchestrator: عندما `matched_entry is not None`، يجب أن يبث الـ "
    "monolith المحتوى المُفهرَس النظيف *قبل* محاولة orchestrator-service.",
    "Conversation context: عند سؤال شرح/استفسار بدون مرجع صريح، يجب فحص "
    "`history_messages` أولاً قبل اللجوء إلى retriever عام.",
    'No leakage: لا يُرسل JSON envelope (مثل `{"المصدر":"...","التمرين":"..."}`) '
    "للمستخدم. الـ caller المسؤول هو `_extract_human_readable_response`.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Explanation Doctrine
# ─────────────────────────────────────────────────────────────────────────────
# قواعد الشرح المُحسَّنة (v2.0.0) — تَبني على ISS-080 (D-068) وتُضيف:
#   - وضوح اللغة (عربية فصحى نقية، لا خلط)
#   - LaTeX إلزامي للرياضيات
#   - بنية الإجابة: فهم → خطة → تنفيذ → تحقق → تفسير
#   - منع التكرار الحرفي للإجابة النموذجية
# ─────────────────────────────────────────────────────────────────────────────

EXPLANATION_DOCTRINE: Final[tuple[str, ...]] = (
    # — الاعتماد على الإجابة النموذجية —
    "اعتمد على الإجابة النموذجية كـ *حُجّة* للنتائج العددية والصيغ النهائية.",
    "لا تنسخ الإجابة النموذجية حرفياً — اشرح *لماذا* كل خطوة تقود للنتيجة.",
    "أرقام الإجابة النموذجية مُلزِمة. لا تخترع نتائج بديلة.",
    "صيغ LaTeX من الإجابة النموذجية مُلزِمة. لا تُعد صياغتها برموز مختلفة.",
    # — نطاق الشرح —
    "إذا كان الطالب طلب جزءاً محدداً (I/II/III/أ/ب/ج)، اقتصر عليه ولا تشرح غيره.",
    # — منهجية الشرح —
    "اشرح القاعدة المُستخدمة (لوبيتال، داربو، التكامل بالتجزئة، نظرية القيمة "
    "الوسيطية...) قبل تطبيقها.",
    "اربط بين خطوات الإجابة بـ «لأن ... إذن ...» لتوضيح المنطق التسلسلي.",
    "في النهاية: تحقق نظري سريع («بفحص نقطة x=0 نلاحظ...») + تفسير هندسي/فيزيائي.",
    # — اللغة والشكل (D-069) —
    "اللغة عربية فصحى نقية. لا كلمات روسية/صينية/إسبانية مُسرَّبة. "
    "(يُطبَّق `sanitize_response` نهاية كل بث للضمان).",
    "كل رمز رياضي يُكتب بـ LaTeX داخل `$...$` (سطر) أو `$$...$$` (كتلة). النص العادي يبقى نصاً.",
    "النتيجة النهائية في `$$\\boxed{...}$$` (أو ما يكافئها).",
)


# ─────────────────────────────────────────────────────────────────────────────
# Model Answer Reliance Rules
# ─────────────────────────────────────────────────────────────────────────────
# قواعد رسمية لكيفية الاعتماد على الإجابة النموذجية أثناء الشرح المفصل.
# هذه قواعد *أحكم* من EXPLANATION_DOCTRINE — لا تُكسر بدون ADR.
# ─────────────────────────────────────────────────────────────────────────────

MODEL_ANSWER_RELIANCE_RULES: Final[tuple[str, ...]] = (
    # — مبدأ الاحتجاج (citation principle) —
    "الإجابة النموذجية هي *مرجع الحُجَّة*. كل نتيجة عددية يجب أن تُحتَجَّ بها.",
    # — الأرقام (numeric invariants) —
    "كل قيمة عددية في الشرح يجب أن تطابق نظيرتها في الإجابة النموذجية. "
    "مثال: لو الإجابة تقول `g'(x) = (x+2)e^(-x)`، الشرح لا يكتب "
    "`g'(x) = (x+2)·e^(-x)` بصيغة مختلفة فحسب — بل نفس الصيغة بالضبط.",
    # — الصيغ الرمزية —
    "الصيغ النهائية (limits, derivatives, integrals) المكتوبة في الإجابة "
    "تُحفَظ كما هي. الشرح يضيف *لماذا* وليس *كيف نُعيد كتابتها*.",
    # — التحقق (verification) —
    "بعد كل خطوة كبيرة، تَحقَّق أن النتيجة المستنبطة تطابق الإجابة النموذجية. "
    "إن لم تطابق، فالشرح غير صحيح ويجب تعديله، لا تعديل الإجابة النموذجية.",
    # — المنطقة الحرة (interpretive freedom) —
    "الشرح حر في:\n"
    "  - اختيار ترتيب الأفكار التعليمية.\n"
    "  - إضافة تذكيرات بقواعد سابقة (مثلاً تذكير بقاعدة لوبيتال قبل تطبيقها).\n"
    "  - إضافة تفسيرات هندسية/فيزيائية للنتيجة.\n"
    "  - استخدام أمثلة عددية مساعدة (مع تأشيرها كـ «مثال توضيحي»).",
    # — المنطقة الممنوعة (forbidden zone) —
    "الشرح ممنوع من:\n"
    "  - تعديل النتائج العددية في الإجابة النموذجية.\n"
    "  - إعادة صياغة الصيغ بشكل مختلف عن الإجابة النموذجية.\n"
    "  - نسخ الإجابة النموذجية حرفياً (يجب وجود قيمة تعليمية مضافة).\n"
    "  - تجاهل أجزاء من الإجابة النموذجية إذا كانت مطلوبة في السؤال.",
    # — الحالة الخاصة: الإجابة النموذجية مفقودة —
    "إذا لم تتوفر الإجابة النموذجية في `full_content`، الـ Skill يُرجِع "
    "`SkillFailure(reason='no_explanation_context')` بدلاً من توليد شرح "
    "بدون مرجع حُجَّة.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Detailed Explanation Rules — الشرح المفصل للطالب
# ─────────────────────────────────────────────────────────────────────────────
# هذه القواعد تُكمِّل EXPLANATION_DOCTRINE بضوابط الـ *حجم* و *التدريج*
# لكل سؤال نوع. يُستخدمها `_classify_question_budget` في `local_graph.py`
# لتخصيص `max_tokens` المناسب.
# ─────────────────────────────────────────────────────────────────────────────

DETAILED_EXPLANATION_RULES: Final[tuple[str, ...]] = (
    # — السؤال المفهومي (concept) —
    "سؤال «ماذا نقصد بـ X» / «ما هو معنى X» = شرح قصير (≤ 350 token).",
    "السؤال المفهومي يبدأ بـ تعريف صريح، ثم مثال واحد، ثم تطبيق على التمرين.",
    # — السؤال التبريري (justification) —
    "سؤال «لماذا X» / «علِّل X» = شرح متوسط (≤ 450 token).",
    "السؤال التبريري يبدأ بـ القاعدة، ثم تطبيقها على بيانات التمرين، "
    "ثم استنتاج النتيجة المُحتجة بها.",
    # — السؤال المنهجي (method) —
    "سؤال «كيف نُثبت X» / «كيف نحسب X» = شرح موسَّع (≤ 600 token).",
    "السؤال المنهجي يبدأ بـ المنهجية العامة، ثم تطبيقها على بيانات التمرين، "
    "ثم النتيجة في `$$\\boxed{...}$$`.",
    # — السؤال الافتراضي (default) —
    "سؤال «اشرح ...» بدون تخصيص = شرح متوازن (≤ 700 token).",
    # — السؤال الشامل (full) —
    "سؤال «اشرح التمرين كاملاً» = شرح طويل (≤ 900 token).",
    "الشرح الشامل يَطوي كل الأجزاء (I/II/III) بفقرات منفصلة، كل واحدة مُختصرة.",
    # — قواعد تنسيقية موحَّدة —
    "كل خطوة تبدأ بـ رقم (1) (2) (3) لتسهيل المتابعة.",
    "العناوين الفرعية بـ `### الجزء I` / `### الخطوة 1` لتفصيل البصري.",
    "الفرضيات بـ `**فرضية:**`، النتائج بـ `**نتيجة:**`.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Skill Doctrine Manifest (للـ CI gate)
# ─────────────────────────────────────────────────────────────────────────────

#: All-in-one manifest يُصدِّره الـ Skill module للـ CI gate لفحص الـ drift.
SKILL_DOCTRINE_MANIFEST: Final[dict[str, dict[str, object]]] = {
    "retrieval": {
        "version": RETRIEVAL_DOCTRINE_VERSION,
        "rules_count": len(RETRIEVAL_DOCTRINE),
        "consumed_by": (
            "BACExerciseSkill._retrieve",
            "orchestrator_client._stream_local_retrieval_response",
            "exercise_retrieval.detect_exercise_retrieval",
        ),
    },
    "explanation": {
        "version": EXPLANATION_DOCTRINE_VERSION,
        "rules_count": len(EXPLANATION_DOCTRINE),
        "consumed_by": (
            "BACExerciseSkill._explain",
            "local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT",
            "BACSkillExplanationOutput.methodology_handle",
        ),
    },
    "model_answer_reliance": {
        "version": MODEL_ANSWER_RELIANCE_VERSION,
        "rules_count": len(MODEL_ANSWER_RELIANCE_RULES),
        "consumed_by": (
            "BACExerciseSkill._explain",
            "local_graph.run_local_graph_with_exercise_context",
        ),
    },
    "detailed_explanation": {
        "version": DETAILED_EXPLANATION_VERSION,
        "rules_count": len(DETAILED_EXPLANATION_RULES),
        "consumed_by": ("local_graph._classify_question_budget",),
    },
}


def get_retrieval_doctrine_summary() -> str:
    """يُرجِع doctrine الاستدعاء كنص قصير (للاستخدام في prompts / logs)."""
    return " | ".join(RETRIEVAL_DOCTRINE)


def get_explanation_doctrine_summary() -> str:
    """يُرجِع doctrine الشرح كنص قصير (للاستخدام في system prompts)."""
    return " | ".join(EXPLANATION_DOCTRINE)


def get_model_answer_reliance_summary() -> str:
    """يُرجِع doctrine الاحتجاج بالإجابة النموذجية (للـ prompts)."""
    return " | ".join(MODEL_ANSWER_RELIANCE_RULES)


def get_detailed_explanation_summary() -> str:
    """يُرجِع doctrine الشرح المفصل (للـ prompts)."""
    return " | ".join(DETAILED_EXPLANATION_RULES)


def list_all_doctrines() -> dict[str, dict[str, object]]:
    """يُرجِع manifest كامل لكل الـ doctrines + versions + consumers (للـ CI)."""
    return SKILL_DOCTRINE_MANIFEST


__all__ = [
    "DETAILED_EXPLANATION_RULES",
    "DETAILED_EXPLANATION_VERSION",
    "EXPLANATION_DOCTRINE",
    "EXPLANATION_DOCTRINE_VERSION",
    "MODEL_ANSWER_RELIANCE_RULES",
    "MODEL_ANSWER_RELIANCE_VERSION",
    # Doctrines
    "RETRIEVAL_DOCTRINE",
    # Versions
    "RETRIEVAL_DOCTRINE_VERSION",
    # Manifest
    "SKILL_DOCTRINE_MANIFEST",
    "get_detailed_explanation_summary",
    "get_explanation_doctrine_summary",
    "get_model_answer_reliance_summary",
    # Helpers
    "get_retrieval_doctrine_summary",
    "list_all_doctrines",
]
