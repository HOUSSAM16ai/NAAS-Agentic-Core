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

    2026-05-19 (D-070): تطوير منظومة Skills — إضافة:
    - CONTENT_INVOCATION_DOCTRINE: بروتوكول استدعاء المحتوى التعليمي خطوة بخطوة.
    - MODEL_ANSWER_EXPLANATION_DOCTRINE: كيفية شرح الإجابة النموذجية للطالب.
    - STEP_BY_STEP_EXPLANATION_RULES: قواعد الشرح خطوة بخطوة.
    - SKILL_INVOCATION_PROTOCOL: بروتوكول استدعاء الـ Skills.
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
# Content Invocation Doctrine (D-070)
# ─────────────────────────────────────────────────────────────────────────────
# بروتوكول استدعاء المحتوى التعليمي — يحدد الخطوات الإلزامية التي يجب أن
# يتبعها أي Skill أو handler عند استدعاء محتوى من `knowledge_base/`.
# المُستفيدون: `BACExerciseSkill`, `local_graph`, `orchestrator_client`.
# ─────────────────────────────────────────────────────────────────────────────

CONTENT_INVOCATION_DOCTRINE_VERSION: Final[str] = "1.0.0"

CONTENT_INVOCATION_DOCTRINE: Final[tuple[str, ...]] = (
    # — الخطوة 1: تحديد النية (Intent Classification) —
    "الخطوة 1 — تحديد النية: قبل أي استدعاء، صنِّف نية الطالب إلى: "
    "(retrieval) طلب التمرين | (explanation) طلب شرح | (concept) سؤال مفهومي. "
    "النية تحدد الـ Skill المُستدعى.",
    # — الخطوة 2: تحديد المرجع (Reference Resolution) —
    "الخطوة 2 — تحديد المرجع: ابحث عن مرجع صريح (سنة + دورة + رقم تمرين) "
    "في السؤال الحالي أولاً، ثم في `history_messages` آخر 3 رسائل. "
    "إن لم يوجد مرجع صريح → `reference=None` → fallback للـ LLM العام.",
    # — الخطوة 3: الفهرسة (Index Lookup) —
    "الخطوة 3 — الفهرسة: مع `reference != None`، ابحث في `knowledge_index` "
    "بـ (year, session, subject_number, exercise_number). "
    "الفهرس يُرجع `matched_entry: ExerciseEntry | None`.",
    # — الخطوة 4: تحميل الملف (File Load) —
    "الخطوة 4 — تحميل الملف: مع `matched_entry != None`، حمِّل ملفاً واحداً "
    "بالضبط عبر `load_exercise_content(matched_entry.file_path)`. "
    "لا scan على المجلد. لا قراءة ملفات إضافية.",
    # — الخطوة 5: التنظيف (Display Strip) —
    "الخطوة 5 — التنظيف: مرِّر المحتوى عبر `format_exercise_for_display()` "
    "لإزالة: YAML frontmatter، أقسام الإجابة النموذجية، علامات chunk الداخلية. "
    "المُخرَج للمستخدم يجب أن يكون نصاً تعليمياً نظيفاً فقط.",
    # — الخطوة 6: البث (Streaming) —
    "الخطوة 6 — البث: ابثّ المحتوى النظيف عبر `assistant_delta` envelopes. "
    "حافظ على سلامة LaTeX: لا تقطع `$...$` أو `$$...$$` بين chunks.",
    # — الخطوة 7: السياق (Context Injection) —
    "الخطوة 7 — السياق: إذا كانت النية (explanation)، أضف `full_content` "
    "(يشمل الإجابة النموذجية) إلى سياق الـ LLM. "
    "لا تُرسل `full_content` للمستخدم مباشرة — فقط للـ LLM.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Model Answer Explanation Doctrine (D-070)
# ─────────────────────────────────────────────────────────────────────────────
# كيفية شرح الإجابة النموذجية للطالب — يُكمِّل EXPLANATION_DOCTRINE بتفاصيل
# المنهجية التعليمية لكل نوع من أنواع الأسئلة في بكالوريا الجزائر.
# ─────────────────────────────────────────────────────────────────────────────

MODEL_ANSWER_EXPLANATION_VERSION: Final[str] = "1.0.0"

MODEL_ANSWER_EXPLANATION_DOCTRINE: Final[tuple[str, ...]] = (
    # — مرحلة الفهم (Understanding Phase) —
    "مرحلة الفهم: ابدأ بـ «ماذا يطلب السؤال؟» — اقرأ المطلوب بصوت عالٍ "
    "للطالب (جملة واحدة). هذا يُثبِّت الهدف قبل الشرح.",
    # — مرحلة الأدوات (Tools Phase) —
    "مرحلة الأدوات: اذكر القاعدة/النظرية/الأداة الرياضية المُستخدمة "
    "(مثال: «نستخدم قاعدة لوبيتال لأن النهاية من الشكل 0/0»). "
    "لا تطبِّق الأداة قبل أن تُعرِّفها.",
    # — مرحلة التطبيق (Application Phase) —
    "مرحلة التطبيق: طبِّق الأداة على بيانات التمرين خطوة بخطوة. "
    "كل خطوة في سطر منفصل. كل رمز رياضي في LaTeX. "
    "اربط بين الخطوات بـ «إذن» / «ومنه» / «بالتعويض».",
    # — مرحلة التحقق (Verification Phase) —
    "مرحلة التحقق: بعد الوصول للنتيجة، تحقق منها بطريقة مختلفة "
    "(مثال: تعويض قيمة في المعادلة الأصلية، أو فحص الإشارة، "
    "أو التحقق من الوحدات في الفيزياء).",
    # — مرحلة التفسير (Interpretation Phase) —
    "مرحلة التفسير: اختم بـ «ماذا تعني هذه النتيجة؟» — تفسير هندسي "
    "(مثال: «هذا يعني أن الدالة تتزايد على المجال...») أو فيزيائي "
    '(مثال: «هذا يعني أن الجسم يتسارع بمعدل...").',
    # — قواعد خاصة بالرياضيات —
    "في الرياضيات: كل نتيجة وسيطة تُكتب في `$...$`. "
    "النتيجة النهائية في `$$\\boxed{...}$$`. "
    "الجداول (جدول الإشارات، جدول التغيرات) تُرسم بـ Markdown.",
    # — قواعد خاصة بالفيزياء —
    "في الفيزياء: كل معادلة تُكتب أولاً بالرموز، ثم بالتعويض العددي، "
    "ثم بالنتيجة مع الوحدة. مثال: $v = d/t = 100/5 = 20 \\text{ m/s}$.",
    # — قواعد خاصة بالعلوم الطبيعية —
    "في العلوم الطبيعية: الشرح يتبع منطق السبب والنتيجة. "
    "كل استنتاج يُبنى على ملاحظة أو تجربة مذكورة في التمرين.",
    # — التكيف مع مستوى الطالب —
    "إذا أعاد الطالب السؤال أو قال «لم أفهم»: أعِد الشرح بمثال عددي "
    "أبسط أولاً، ثم انتقل للتمرين الأصلي. لا تكرر نفس الشرح حرفياً.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Step-by-Step Explanation Rules (D-070)
# ─────────────────────────────────────────────────────────────────────────────
# قواعد الشرح خطوة بخطوة — تُطبَّق على كل شرح مفصل بغض النظر عن النوع.
# هذه القواعد تُكمِّل DETAILED_EXPLANATION_RULES بضوابط التسلسل المنطقي.
# ─────────────────────────────────────────────────────────────────────────────

STEP_BY_STEP_EXPLANATION_VERSION: Final[str] = "1.0.0"

STEP_BY_STEP_EXPLANATION_RULES: Final[tuple[str, ...]] = (
    # — التسلسل المنطقي —
    "كل خطوة تنبثق من السابقة: لا قفز منطقي. إذا كانت الخطوة n تعتمد على "
    'نتيجة الخطوة n-2، اذكر ذلك صراحةً («من الخطوة 2 وجدنا أن...").',
    # — الترقيم الإلزامي —
    "الترقيم إلزامي: **الخطوة 1:** / **الخطوة 2:** / ... "
    "لا شرح بدون ترقيم واضح. الطالب يجب أن يعرف أين هو في الشرح.",
    # — الحجم المتناسب —
    "كل خطوة تحتل 2-4 أسطر. خطوة أطول من 6 أسطر = يجب تقسيمها. "
    "خطوة أقصر من سطر = يجب دمجها مع المجاورة.",
    # — الانتقالات (Transitions) —
    "استخدم كلمات الانتقال: «إذن» (استنتاج)، «ومنه» (تحويل رياضي)، "
    "«بالتعويض» (تطبيق عددي)، «نلاحظ أن» (ملاحظة)، "
    "«نستنتج أن» (استنتاج نهائي).",
    # — التحقق الذاتي —
    "في نهاية كل خطوة كبيرة: جملة تحقق قصيرة بين قوسين (مثال: «(تحقق: بتعويض x=0 نجد 0 = 0 ✓)»).",
    # — التكيف مع نوع السؤال —
    "سؤال الإثبات (prove): ابدأ من المعطيات وانتهِ بالمطلوب. "
    "لا تبدأ من المطلوب وترجع للمعطيات (circular reasoning).",
    "سؤال الحساب (calculate): ابدأ بالصيغة العامة، ثم التعويض، ثم النتيجة.",
    "سؤال الدراسة (study): ابدأ بتحديد المجال، ثم الاشتقاق، ثم الجدول، ثم الرسم (إن طُلب).",
    # — الخاتمة الإلزامية —
    "كل شرح ينتهي بـ «**الخلاصة:**» — جملة واحدة تلخص النتيجة الرئيسية. "
    "هذا يُثبِّت المعلومة في ذاكرة الطالب.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Skill Invocation Protocol (D-070)
# ─────────────────────────────────────────────────────────────────────────────
# بروتوكول استدعاء الـ Skills — يحدد كيف يجب أن يستدعي الـ orchestrator
# أو الـ monolith أي Skill، وما هي الضمانات المطلوبة.
# ─────────────────────────────────────────────────────────────────────────────

SKILL_INVOCATION_PROTOCOL_VERSION: Final[str] = "1.0.0"

SKILL_INVOCATION_PROTOCOL: Final[tuple[str, ...]] = (
    # — قبل الاستدعاء (Pre-invocation) —
    "قبل استدعاء أي Skill: تحقق من توفر المدخلات الإلزامية. "
    "Skill مفقود مدخل إلزامي → `SkillFailure(reason='missing_input')` فوراً. "
    "لا تستدعِ Skill بمدخلات ناقصة.",
    # — الاستدعاء (Invocation) —
    "الاستدعاء عبر HTTP فقط (لا import مباشر بين microservices). "
    "كل طلب يحمل `X-Correlation-ID` للتتبع الموزع. "
    "timeout إلزامي: ≤ 30s للـ Skills التي تستدعي LLM، ≤ 5s للـ Skills الأخرى.",
    # — معالجة النتيجة (Result Handling) —
    "نتيجة الـ Skill إما `SkillSuccess` أو `SkillFailure`. "
    "لا تفترض النجاح. تحقق من النوع قبل الاستخدام.",
    # — الـ Fallback —
    "كل Skill يجب أن يملك fallback mode: إذا فشل الـ Skill الأساسي، "
    "يُرجع `SkillFailure` مع `fallback_available=True` ليُعلم الـ caller "
    "بإمكانية الاستدعاء البديل.",
    # — القياس (Metrics) —
    "كل استدعاء Skill يُسجَّل في Prometheus: "
    "`cogniforge_{skill}_invocations_total{mode, status}` + "
    "`cogniforge_{skill}_duration_seconds{mode}`. "
    "لا Skill بدون metrics.",
    # — العزل (Isolation) —
    "Skill لا يستدعي Skill آخر مباشرة. كل تنسيق يمر عبر orchestrator. "
    "هذا يمنع circular dependencies ويُبسِّط الـ debugging.",
)


# ─────────────────────────────────────────────────────────────────────────────
# BKT Cognitive Doctrine (D-074 / Protocol V6.0) — الطبقة المعرفية الأساسية
# ─────────────────────────────────────────────────────────────────────────────
BKT_COGNITIVE_DOCTRINE_VERSION: Final[str] = "1.0.0"

#: قوانين غير قابلة للكسر تحكم طبقة التتبّع المعرفي البايزي (BKT) — الأساس
#: المعرفي لكل skill تربوي مستقبلي في منصة E-TAALEEM.
BKT_COGNITIVE_DOCTRINE: Final[tuple[str, ...]] = (
    "BKT هي الطبقة المعرفية الأساسية لكل skill تربوي مستقبلي — أي قدرة تكيّفية "
    "(تدرّج الصعوبة، التلميحات، مسار التعلّم) تُبنى فوق student_mastery_probability.",
    "Zero Cognitive Overload: الجمهور طلاب بكالوريا — الرموز المجرّدة (A, B|A, Ā) "
    "ممنوعة نهائياً في عُقَد الواجهة التوليدية.",
    "Abstraction Ban: كل مكوّن UI توليدي يستخدم نموذج الاستخراج الهجين "
    "(deterministic-first ثم LLM عند الحاجة) لإخراج تسميات ملموسة بشرية "
    "(كرة حمراء، سحب ناجح، قطعة معيبة) — وحتى الـ fallback ملموس، لا حرف مجرّد.",
    "BKT سجل append-only فقط — كل تفاعل صف جديد؛ لا تحديث في المكان. الإتقان "
    "السابق يُقرأ من آخر صف لنفس (user_id, concept_id). يحفظ السلسلة الزمنية كاملة.",
    "المخطط الإلزامي: concept_id + cognitive_load_estimate (low/medium/high) + "
    "student_mastery_probability ∈ [0,1] + interaction_timestamp.",
    "student_mastery_probability يُحدَّث بمعادلة BKT بايزية حتمية "
    "(P_L0/P_T/P_S/P_G) — نفس المدخلات تُنتج نفس المخرجات (قابل للاختبار).",
    "BKT لا يكسر المحادثة أبداً — كل استدعاء معزول في try/except بجلسة DB مستقلة.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Probability Calculation Doctrine (D-075 — Protocol V14.0 / Generative UI)
# ─────────────────────────────────────────────────────────────────────────────

PROBABILITY_CALCULATION_DOCTRINE_VERSION: Final[str] = "1.2.0"

#: قوانين غير قابلة للكسر تحكم محرّك حساب الاحتمالات الحتمي الذي يغذّي شجرة
#: الاحتمالات التوليدية. الخلفية لا تُخرج HTML ولا قيماً وهمية — تحسب كسوراً
#: حقيقية من تركيبة المسألة العربية (Protocol V14.0 §3).
PROBABILITY_CALCULATION_DOCTRINE: Final[tuple[str, ...]] = (
    "حساب حقيقي لا قيم وهمية: P(الحدث) = العدد / المجموع كـ كسر مختزَل دقيق "
    "(مثل 4/11) — ممنوع منعاً باتاً إخراج 0.5 افتراضية حين تتوفّر التركيبة.",
    "حتمي تماماً: نفس نص المسألة يُنتج نفس الكسور دائماً — لا LLM، لا عشوائية، "
    "قابل للاختبار بـ pytest عادي.",
    "استخراج التركيبة من العربية: أعداد رقمية وكلمات (كرتان=2، أربع=4، خمس=5) "
    "مقرونة بالكيانات الملموسة (حمراء، بيضاء، خضراء) — لا رموز مجرّدة.",
    "السحب بدون إرجاع يُحدِّث المقام والبسط شرطياً ((العدد-1)/(المجموع-1))؛ "
    "السحب مع الإرجاع يُبقي الاحتمال ثابتاً — يُكتشف الوضع من نص المسألة.",
    "كل عقدة شجرة تحمل الكسر الدقيق (p_num/p_den) إضافةً للقيمة العشرية، "
    "فتُصيّر الواجهة 4/11 تماماً دون إعادة بناء تقريبية من العشري.",
    "Abstraction Ban: تسميات العُقَد ملموسة بشرية مستخرَجة من السياق — وحتى "
    "fallback المجموع المجهول لا يُخرج حرفاً مجرّداً.",
    "العقد فصل صارم: المحرّك يُرجع Pydantic منظَّماً فقط؛ التصيير مسؤولية "
    "الواجهة (RSC) — الخلفية لا تعرف شيئاً عن SVG أو HTML.",
    "الموجِّه التربوي (V19.0): «دفعة واحدة» (سحب آني) = تأليفي C(n,k) → مكوّن "
    "combinations_visualizer؛ «على التوالي» (تتابعي) → probability_tree. ممنوع "
    "فرض شجرة تتابعية على مسألة آنية (كارثة تربوية).",
    "جذر الشجرة بلا احتمال (لا 1/1 وهمي)، ولا كسر منحلّ (1/0) يصل للطالب أبداً.",
    "استخراج الكيانات الملموسة (ISS-083): يقبل اسم الرقم الصريح المستقل فقط "
    "(«بطاقة رقم 1»، «تحمل الرقم 2») ويرفض صفة «مرقمة/مرقمتان/مرقم» (تعني "
    "«مُعلَّمة بـ» وتصف ترقيم العناصر لا نوعها). مطابقة «رقم» كسلسلة فرعية داخل "
    "«مرقمة» كانت تُنتج كياناً زائفاً («كرة رقم 0») يُضخّم المجموع (17 بدل 11) "
    "ويُخرج كسوراً خاطئة وشجرة تتابعية مضلِّلة لمسألة سحب آني — كارثة تربوية.",
)


# ─────────────────────────────────────────────────────────────────────────────
# Impossible Case UX Doctrine (D-082)
# ─────────────────────────────────────────────────────────────────────────────
# قواعد تجربة الحالة المستحيلة — تُطبَّق عند requested > bag_count.
# المُستفيدون: content-retrieval-skill /impossible-case + frontend renderer.
# ─────────────────────────────────────────────────────────────────────────────

#: نسخة doctrine الحالة المستحيلة.
IMPOSSIBLE_CASE_DOCTRINE_VERSION: Final[str] = "1.0.0"

IMPOSSIBLE_CASE_DOCTRINE: Final[tuple[str, ...]] = (
    "لا تبدأ بالرياضيات: المرحلة 1 و2 و3 خالية تماماً من المعادلات والصيغ.",
    "مشهد واحد في كل مرحلة: لا تعرض أكثر من فكرة واحدة في أي شاشة.",
    "لا شجرة احتمالات في الحالة المستحيلة: الشجرة تظهر فقط للحالات الممكنة.",
    "السؤال الحدسي (المرحلة 2) يجب أن يكون مباشراً وبسيطاً — لا معادلة، لا صفر.",
    "الحركة البصرية (المرحلة 3) قصيرة وهادئة — shake ≤ 600ms، لا تكرار.",
    "الرسالة التربوية (المرحلة 4) واحدة فقط — واضحة ولطيفة، تذكر الأعداد الفعلية.",
    "deep_dive اختياري: يُعرض فقط عند ضغط المستخدم على 'اشرح لي أكثر'.",
    "backend يُرسل contract بصري فقط (حالة + بيانات + رسالة) — لا HTML، لا SVG.",
    "frontend مسؤول عن تحويل الـ contract إلى قصة بصرية — لا خلط منطق بحركة.",
    "الشرح الرياضي العميق (deep_dive) يحتوي: formula + explanation + why_zero.",
)


def get_impossible_case_summary() -> str:
    """يُرجِع ملخصاً موجزاً لـ doctrine الحالة المستحيلة."""
    return (
        f"[v{IMPOSSIBLE_CASE_DOCTRINE_VERSION}] "
        f"{len(IMPOSSIBLE_CASE_DOCTRINE)} قاعدة — "
        "4 مراحل بصرية، لا رياضيات قبل الفهم الحدسي، deep_dive اختياري."
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
    "content_invocation": {
        "version": CONTENT_INVOCATION_DOCTRINE_VERSION,
        "rules_count": len(CONTENT_INVOCATION_DOCTRINE),
        "consumed_by": (
            "BACExerciseSkill._retrieve",
            "local_graph.run_local_graph_with_exercise_context",
            "orchestrator_client._stream_local_retrieval_response",
        ),
    },
    "model_answer_explanation": {
        "version": MODEL_ANSWER_EXPLANATION_VERSION,
        "rules_count": len(MODEL_ANSWER_EXPLANATION_DOCTRINE),
        "consumed_by": (
            "BACExerciseSkill._explain",
            "local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT",
        ),
    },
    "step_by_step_explanation": {
        "version": STEP_BY_STEP_EXPLANATION_VERSION,
        "rules_count": len(STEP_BY_STEP_EXPLANATION_RULES),
        "consumed_by": (
            "local_graph._classify_question_budget",
            "BACExerciseSkill._explain",
        ),
    },
    "skill_invocation_protocol": {
        "version": SKILL_INVOCATION_PROTOCOL_VERSION,
        "rules_count": len(SKILL_INVOCATION_PROTOCOL),
        "consumed_by": (
            "orchestrator_client.chat_with_agent",
            "local_graph.run_local_graph",
        ),
    },
    "answer_quality": {
        "version": "1.0.0",
        "rules_count": 6,
        "consumed_by": (
            "AnswerQualitySkill.evaluate",
            # D-073 (2026-05-19): wired into the live monolith path.
            "local_graph._apply_answer_quality_skill",
        ),
    },
    "bkt_cognitive": {
        "version": BKT_COGNITIVE_DOCTRINE_VERSION,
        "rules_count": len(BKT_COGNITIVE_DOCTRINE),
        "consumed_by": (
            # D-074 (Protocol V6.0): الطبقة المعرفية الأساسية — موصولة حيّاً.
            "BKTEngine.evaluate",
            "bkt_persistence.BKTAnalyticsService.evaluate_and_record",
            "customer_chat._evaluate_and_emit_bkt",
            "orchestrator_client._build_probability_tree_props",
        ),
    },
    "probability_calculation": {
        "version": PROBABILITY_CALCULATION_DOCTRINE_VERSION,
        "rules_count": len(PROBABILITY_CALCULATION_DOCTRINE),
        "consumed_by": (
            # D-075 (Protocol V14.0): محرّك الاحتمالات الحتمي — موصول حيّاً.
            "ProbabilityCalculatorSkill.analyze",
            "orchestrator_client._build_probability_tree_props",
            # D-078 (Protocol V19.0): الموجِّه التربوي (آني/تتابعي) — موصول حيّاً.
            "orchestrator_client._build_calculated_ui",
        ),
    },
    "impossible_case": {
        "version": IMPOSSIBLE_CASE_DOCTRINE_VERSION,
        "rules_count": len(IMPOSSIBLE_CASE_DOCTRINE),
        "consumed_by": (
            # D-082: content-retrieval-skill /impossible-case endpoint.
            "content_retrieval_skill.src.impossible_case.analyze_impossible_case",
            # frontend: ImpossibleCaseRenderer (4 مراحل بصرية).
            "frontend.components.ImpossibleCaseRenderer",
        ),
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


def get_content_invocation_summary() -> str:
    """يُرجِع بروتوكول استدعاء المحتوى كنص قصير (للـ prompts / logs)."""
    return " | ".join(CONTENT_INVOCATION_DOCTRINE)


def get_model_answer_explanation_summary() -> str:
    """يُرجِع doctrine شرح الإجابة النموذجية (للـ system prompts)."""
    return " | ".join(MODEL_ANSWER_EXPLANATION_DOCTRINE)


def get_step_by_step_summary() -> str:
    """يُرجِع قواعد الشرح خطوة بخطوة (للـ prompts)."""
    return " | ".join(STEP_BY_STEP_EXPLANATION_RULES)


def get_skill_invocation_protocol_summary() -> str:
    """يُرجِع بروتوكول استدعاء الـ Skills (للـ orchestrator / logs)."""
    return " | ".join(SKILL_INVOCATION_PROTOCOL)


def get_bkt_cognitive_summary() -> str:
    """يُرجِع doctrine الطبقة المعرفية BKT كنص قصير (للـ logs / prompts)."""
    return " | ".join(BKT_COGNITIVE_DOCTRINE)


def get_probability_calculation_summary() -> str:
    """يُرجِع doctrine حساب الاحتمالات كنص قصير (للـ logs / prompts)."""
    return " | ".join(PROBABILITY_CALCULATION_DOCTRINE)


def build_exercise_explanation_prompt() -> str:
    """يبني system prompt شرح التمرين مباشرةً من الـ doctrine.

    D-071 (2026-05-19): هذه الدالة هي **single source of truth** للـ prompt
    المُرسَل للـ LLM عند شرح تمارين البكالوريا. أي تغيير في الـ doctrine
    ينعكس تلقائياً على الـ prompt — لا drift ممكن.

    القيود الإلزامية (D-067):
    - الـ prompt يجب أن يبقى < 1000 حرف (النماذج المجانية تدخل reasoning-mode
      مع prompts > 1500 حرف).
    - لا box-drawing chars (U+2500–U+257F) — تُربك tokenizers النماذج المجانية.
    - لا تكرار — كل قاعدة تُذكر مرة واحدة فقط.

    المُستهلكون:
    - `app.services.chat.local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT`
    - `microservices.conversation_service.src.conversation_graph`
    """
    # الجزء الثابت — هوية الأستاذ + قاعدة اللغة (لا تتغير مع الـ doctrine)
    header = "أنت أستاذ رياضيات للبكالوريا الجزائرية.\nاشرح للطالب كيف يفكر، لا تكتفِ بالحساب.\n\n"

    # قواعد إلزامية من EXPLANATION_DOCTRINE (أول 5 قواعد — الأكثر أهمية)
    core_rules = "\n".join(f"{i + 1}. {rule}" for i, rule in enumerate(EXPLANATION_DOCTRINE[:5]))

    # منهجية الشرح من MODEL_ANSWER_EXPLANATION_DOCTRINE (أول 5 مراحل)
    methodology_lines = "\n".join(
        f"- {rule.split(':')[0].strip()}" for rule in MODEL_ANSWER_EXPLANATION_DOCTRINE[:5]
    )

    prompt = header + "قواعد إلزامية:\n" + core_rules + "\n\nمنهجية الشرح:\n" + methodology_lines

    # ضمان عدم تجاوز 1000 حرف (D-067 invariant)
    if len(prompt) > 1000:
        prompt = prompt[:997] + "..."

    return prompt


#: الـ prompt المُبنى من الـ doctrine — يُستخدم في local_graph و conversation_graph.
#: D-071: هذا الثابت هو المرجع الوحيد — لا تعريف prompt محلي في أي ملف آخر.
EXERCISE_EXPLANATION_SYSTEM_PROMPT: Final[str] = build_exercise_explanation_prompt()


def list_all_doctrines() -> dict[str, dict[str, object]]:
    """يُرجِع manifest كامل لكل الـ doctrines + versions + consumers (للـ CI)."""
    return SKILL_DOCTRINE_MANIFEST


__all__ = [
    "BKT_COGNITIVE_DOCTRINE",
    "BKT_COGNITIVE_DOCTRINE_VERSION",
    "CONTENT_INVOCATION_DOCTRINE",
    "CONTENT_INVOCATION_DOCTRINE_VERSION",
    "DETAILED_EXPLANATION_RULES",
    "DETAILED_EXPLANATION_VERSION",
    "EXERCISE_EXPLANATION_SYSTEM_PROMPT",
    "EXPLANATION_DOCTRINE",
    "EXPLANATION_DOCTRINE_VERSION",
    "IMPOSSIBLE_CASE_DOCTRINE",
    "IMPOSSIBLE_CASE_DOCTRINE_VERSION",
    "MODEL_ANSWER_EXPLANATION_DOCTRINE",
    "MODEL_ANSWER_EXPLANATION_VERSION",
    "MODEL_ANSWER_RELIANCE_RULES",
    "MODEL_ANSWER_RELIANCE_VERSION",
    "PROBABILITY_CALCULATION_DOCTRINE",
    "PROBABILITY_CALCULATION_DOCTRINE_VERSION",
    "RETRIEVAL_DOCTRINE",
    "RETRIEVAL_DOCTRINE_VERSION",
    "SKILL_DOCTRINE_MANIFEST",
    "SKILL_INVOCATION_PROTOCOL",
    "SKILL_INVOCATION_PROTOCOL_VERSION",
    "STEP_BY_STEP_EXPLANATION_RULES",
    "STEP_BY_STEP_EXPLANATION_VERSION",
    "build_exercise_explanation_prompt",
    "get_bkt_cognitive_summary",
    "get_content_invocation_summary",
    "get_detailed_explanation_summary",
    "get_explanation_doctrine_summary",
    "get_impossible_case_summary",
    "get_model_answer_explanation_summary",
    "get_model_answer_reliance_summary",
    "get_probability_calculation_summary",
    "get_retrieval_doctrine_summary",
    "get_skill_invocation_protocol_summary",
    "get_step_by_step_summary",
    "list_all_doctrines",
]
