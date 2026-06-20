"""
ConceptDiagnosisSkill — الطبقة 1 (الفهم العصبي) + الطبقة 5 (النموذج العقلي) من
المعمارية الإدراكية العصبية-الرمزية (D-127).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
تحويل سؤال الطالب الفوضوي (+ سياق المحادثة) إلى **زوج معرفي مُقيَّد**:
``(concept, misconception)`` — لا رياضيات، لا أرقام، لا إجابة. مجرّد **تشخيص**.

الأستاذ الحقيقي يرى «ما هو البسط؟»، «لماذا 14؟»، «ما الهدف من 14؟»، «واش راه هاد
14؟» كرسالة **واحدة**: الطالب لا يفهم مفهوم *الحالات الملائمة* (numerator). هذا الـ
Skill يجسّد ذلك الذكاء.

## المعمارية العصبية-الرمزية (D-127)
- **الطبقة 1 (LLM للفهم فقط)**: يصنّف *أيّ* صياغة جديدة → مفهوم. لا يحسب، لا يجيب.
- **الطبقة 5 (النموذج العقلي)**: المخرج ليس المفهوم وحده بل *سبب* الحيرة
  (`misconception`) — يقود اختيار التدخّل السقراطي التالي (الطبقة 4).

## النمط الهجين (deterministic-first ثم LLM — مطابق لـ D-074 Abstraction Ban)
1. خريطة حتمية أولاً (سريعة، صفر خطر) تغطّي الصياغات المعروفة.
2. مُصنّف LLM **محروس** (timeout + enum-validation + fallback حتمي) عند `unknown` فقط —
   يُعيد **كلمة واحدة من الـ enum** حصراً. الهلوسة شبه مستحيلة (مخرج مُقيَّد).

## الاستقلالية (§0.5)
- لا يستورد من Skills أخرى. يستخدم `app.core.ai_gateway.get_ai_client` (core، لا skill).
- التشخيص الحتمي حتمي تماماً (قابل للاختبار بـ pytest عادي).

## القياس (Prometheus)
- `cogniforge_skill_concept_diagnosis_total{concept,misconception,source}` (counter)
- `cogniforge_skill_concept_diagnosis_duration_seconds` (histogram)
"""

from __future__ import annotations

import contextlib
import time
from typing import Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import CONCEPT_DIAGNOSIS_DOCTRINE_VERSION

# ── الـ enum الثابت (الطبقة 1 تُصنّف إليه حصراً) ──────────────────────────────────
Concept = Literal[
    "denominator",  # المقام / 165 / فضاء العينة / كل الطرق
    "numerator",  # البسط / 14 / الحالات الملائمة
    "ratio",  # العلاقة / الفرق بين البسط والمقام / معنى النسبة
    "combinations",  # التوافيق / C(n,k) / ترتيب أم اختيار
    "color_red",  # تأليفات الحمراء (C(4,3)=4)
    "color_green",  # تأليفات الخضراء (C(5,3)=10)
    "color_white",  # البيضاء المستحيلة
    "event_meaning",  # D-128: معنى الحادثة A/B/C/D (ماذا نقصد بالحادثة)
    "full_solution",  # «اشرح السؤال الأول» / حيرة عامة
    "unknown",  # لم يُصنَّف حتمياً ⇒ يُحال للـ LLM
]

Misconception = Literal[
    "sample_space_confusion",  # يخلط البسط بالمقام (14 مقابل 165)
    "fraction_meaning_confusion",  # لا يفهم معنى النسبة (البسط/المقام)
    "order_vs_selection_confusion",  # يظن الترتيب مهمّاً (ترتيب أم توافيق)
    "favourable_outcomes_confusion",  # لا يفهم ما الذي «ينجح» (الحالات الملائمة)
    "none",
]

#: الـ enum كـ frozenset للتحقّق من مخرج الـ LLM (الطبقة 1 الآمنة).
_VALID_CONCEPTS: frozenset[str] = frozenset(
    (
        "denominator",
        "numerator",
        "ratio",
        "combinations",
        "color_red",
        "color_green",
        "color_white",
        "event_meaning",
        "full_solution",
        "unknown",
    )
)

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _normalize(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


# ── الخريطة الحتمية (الطبقة 1، الجزء السريع الآمن) ────────────────────────────────
# الترتيب مهم: الأكثر تحديداً أولاً. كل صياغات المفهوم الواحد → نفس المفهوم.
_NUMERATOR_MARKERS: tuple[str, ...] = (
    "البسط",
    "ما هو البسط",
    "ماذا يمثل البسط",
    "معنى البسط",
    "14",
    "الحالات الملائمة",
    "الحالات المواتية",
    "الحالات التي تنجح",
    "ما الحالات",
)
_DENOMINATOR_MARKERS: tuple[str, ...] = (
    "المقام",
    "ما هو المقام",
    "ماذا يمثل المقام",
    "معنى المقام",
    "165",
    "فضاء العينة",
    "فضاء العيّنة",
    "العدد الكلي",
    "كل الطرق",
    "كل الاحتمالات",
    "كل الامكانات",
)
_RATIO_MARKERS: tuple[str, ...] = (
    "الفرق بين",
    "الفرق",
    "العلاقة",
    "الرابط",
    "النسبة",
    "نقسم",
    "القسمة",
    "البسط والمقام",
    "بسط ومقام",
    "ضعت بين",
    "ضائع بين",
    "تهت بين",
)
_COMBINATIONS_MARKERS: tuple[str, ...] = (
    "التوافيق",
    "توافيق",
    "الترتيب",
    "ترتيب",
    "الاختيار",
    "permutation",
    "combinaison",
    "لماذا نختار",
    "لماذا التوافيق",
)
_FULL_MARKERS: tuple[str, ...] = (
    "اشرح",
    "الحل الكامل",
    "حل التمرين",
    "السؤال الأول",
    "السؤال الاول",
    "كيف أحل",
    "كيف احل",
    "كيف نحل",
)
#: أفعال إجرائية: «لماذا/كيف» معها مع رقم البسط ⇒ numerator (لا ratio) — «لماذا نجمع 4 و10».
_NUMERATOR_PROCEDURAL: tuple[str, ...] = (
    "نجمع",
    "كيف حسبنا 14",
    "كيف نحسب 14",
    "وجدنا 14",
)
#: D-128: معنى الحادثة (A/B/C/D) — «ماذا نقصد بالحادثة A»، «الحادثة A كيف افهمها».
_EVENT_MARKERS: tuple[str, ...] = (
    "الحادثة a",
    "الحادثة b",
    "الحادثة c",
    "الحادثة d",
    "الحدث a",
    "الحدث b",
    "الحدث c",
    "الحدث d",
    "الحادثه a",
    "الحادثه b",
    "الحادثه c",
    "الحادثه d",
    "ماذا نقصد بالحادثة",
    "ماذا نقصد بالحدث",
    "ما معنى الحادثة",
    "ما معنى الحدث",
    "ما هي الحادثة",
    "ما هو الحدث",
    "كيف افهم الحادثة",
    "كيف افهم الحدث",
)


class ConceptDiagnosisInput(RobustBaseModel):
    """مدخلات التشخيص — typed contract."""

    question: str = Field(..., min_length=1, max_length=8000)
    history: list[dict[str, str]] | None = None


class ConceptDiagnosisOutput(RobustBaseModel):
    """مخرج التشخيص: (مفهوم + مفهوم خاطئ) + مصدر. لا رياضيات، لا إجابة."""

    concept: Concept
    misconception: Misconception = "none"
    source: Literal["deterministic", "llm", "fallback"] = "deterministic"


# ── Prometheus metrics ─────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter, Histogram

    if "cogniforge_skill_concept_diagnosis_total" in {m.name for m in REGISTRY.collect()}:
        _diag_total = None
        _diag_duration = None
    else:
        _diag_total = Counter(
            "cogniforge_skill_concept_diagnosis_total",
            "Concept diagnoses, labelled by concept/misconception/source.",
            ["concept", "misconception", "source"],
        )
        _diag_duration = Histogram(
            "cogniforge_skill_concept_diagnosis_duration_seconds",
            "Duration of concept diagnosis in seconds.",
        )

    def _record(concept: str, misconception: str, source: str, duration: float) -> None:
        with contextlib.suppress(Exception):
            if _diag_total is not None:
                _diag_total.labels(
                    concept=concept, misconception=misconception, source=source
                ).inc()
            if _diag_duration is not None:
                _diag_duration.observe(duration)

except Exception:  # pragma: no cover

    def _record(concept: str, misconception: str, source: str, duration: float) -> None:
        pass


def _infer_misconception(concept: str, normalized: str) -> Misconception:
    """الطبقة 5: يستنتج *سبب* الحيرة من المفهوم + إشارات النص (حتمي)."""
    if concept == "numerator":
        # يذكر البسط/14 **و** المقام/165 معاً ⇒ يخلط بينهما (sample_space_confusion).
        if any(m in normalized for m in ("165", "المقام", "فضاء", "كل الطرق")):
            return "sample_space_confusion"
        return "favourable_outcomes_confusion"
    if concept == "denominator":
        if any(m in normalized for m in ("14", "البسط", "الملائمة")):
            return "sample_space_confusion"
        return "none"
    if concept == "ratio":
        return "fraction_meaning_confusion"
    if concept == "combinations":
        return "order_vs_selection_confusion"
    if concept == "event_meaning":
        # D-128: لا يفهم ما الذي «ينجح» في الحادثة (الحالات الملائمة).
        return "favourable_outcomes_confusion"
    return "none"


class ConceptDiagnosisSkill:
    """
    Skill عصبي-رمزي لتشخيص المفهوم + المفهوم الخاطئ (الطبقتان 1 و 5 — D-127).

    عقد دائم (لا يُكسر بدون ADR):
    1. لا رياضيات/أرقام/إجابة في المخرج — مجرّد تشخيص (concept + misconception).
    2. حتمي أولاً؛ LLM محروس فقط عند unknown (مخرج مُقيَّد بالـ enum + timeout + fallback).
    3. لا يستورد من Skills أخرى (§0.5).
    """

    _skill_name: str = "concept_diagnosis"
    doctrine_version: str = CONCEPT_DIAGNOSIS_DOCTRINE_VERSION
    _LLM_TIMEOUT_S: float = 8.0

    @staticmethod
    def diagnose_deterministic(question: str) -> ConceptDiagnosisOutput:
        """الجزء الحتمي السريع — يُرجِع concept=unknown إن لم يُطابق (يُحال للـ LLM)."""
        q = _normalize(question)
        concept: Concept = "unknown"
        # D-128: معنى الحادثة أولاً (أعلى مستوى — «ماذا نقصد بالحادثة A»).
        # ثم الألوان، ثم ratio (مقارنة)، ثم numerator/denominator.
        if any(m in q for m in _EVENT_MARKERS):
            concept = "event_meaning"
        elif any(m in q for m in ("الحمراء", "حمراء", "احمر")):
            concept = "color_red"
        elif any(m in q for m in ("الخضراء", "خضراء", "اخضر")):
            concept = "color_green"
        elif any(m in q for m in ("البيضاء", "بيضاء", "ابيض")):
            concept = "color_white"
        elif any(m in q for m in _RATIO_MARKERS):
            concept = "ratio"
        elif any(m in q for m in _COMBINATIONS_MARKERS):
            concept = "combinations"
        elif any(m in q for m in _NUMERATOR_PROCEDURAL) or any(m in q for m in _NUMERATOR_MARKERS):
            concept = "numerator"
        elif any(m in q for m in _DENOMINATOR_MARKERS):
            concept = "denominator"
        elif any(m in q for m in _FULL_MARKERS):
            concept = "full_solution"
        misconception = _infer_misconception(concept, q)
        return ConceptDiagnosisOutput(
            concept=concept, misconception=misconception, source="deterministic"
        )

    async def diagnose(self, payload: ConceptDiagnosisInput) -> ConceptDiagnosisOutput:
        """يُشخّص: حتمي أولاً؛ LLM محروس عند unknown. لا يرفع استثناءات منطقية."""
        t0 = time.perf_counter()
        result = self.diagnose_deterministic(payload.question)
        if result.concept == "unknown":
            llm_concept = await self._classify_with_llm(payload.question)
            if llm_concept is not None and llm_concept != "unknown":
                result = ConceptDiagnosisOutput(
                    concept=llm_concept,
                    misconception=_infer_misconception(llm_concept, _normalize(payload.question)),
                    source="llm",
                )
        _record(result.concept, result.misconception, result.source, time.perf_counter() - t0)
        return result

    @classmethod
    async def _classify_with_llm(cls, question: str) -> Concept | None:
        """الطبقة 1: مُصنّف LLM محروس — يُعيد كلمة واحدة من الـ enum أو None.

        مخرج مُقيَّد (enum-validation) + timeout + fallback. **لا رياضيات، لا إجابة** —
        مجرّد تصنيف. أي مخرج خارج الـ enum ⇒ None ⇒ يبقى unknown (آمن).
        """
        import asyncio

        try:
            from app.core.ai_gateway import get_ai_client

            system_prompt = (
                "أنت مُصنّف نوايا تعليمية (لا تحلّ، لا تحسب، لا تشرح). صنّف سؤال الطالب "
                "في درس الاحتمالات إلى كلمة واحدة فقط من هذه القائمة، بلا أي نص آخر:\n"
                "denominator (المقام/فضاء العينة/كل الطرق) | numerator (البسط/الحالات "
                "الملائمة) | ratio (الفرق بين البسط والمقام/معنى النسبة) | combinations "
                "(التوافيق/الترتيب) | color_red | color_green | color_white | "
                "event_meaning (يسأل عن معنى الحادثة A/B/C/D) | "
                "full_solution (يريد الحل كاملاً) | unknown.\n"
                "أعِد الكلمة الإنجليزية فقط."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(
                    system_prompt, question.strip()[:600], temperature=0.0
                ),
                timeout=cls._LLM_TIMEOUT_S,
            )
            if not raw or not isinstance(raw, str):
                return None
            token = raw.strip().lower().split()[0].strip(".,:;\"'`") if raw.strip() else ""
            if token in _VALID_CONCEPTS:
                return token  # type: ignore[return-value]
            # ربما أعاد النموذج الكلمة وسط نص — ابحث عن أول مفهوم صالح.
            low = raw.lower()
            for c in _VALID_CONCEPTS:
                if c in low:
                    return c  # type: ignore[return-value]
            return None
        except Exception:  # pragma: no cover — fail-safe (لا يكسر دور الطالب)
            return None


_concept_diagnosis_singleton: ConceptDiagnosisSkill | None = None


def get_concept_diagnosis_skill() -> ConceptDiagnosisSkill:
    """يُرجع نسخة مفردة (lazy singleton)."""
    global _concept_diagnosis_singleton
    if _concept_diagnosis_singleton is None:
        _concept_diagnosis_singleton = ConceptDiagnosisSkill()
    return _concept_diagnosis_singleton


__all__ = [
    "Concept",
    "ConceptDiagnosisInput",
    "ConceptDiagnosisOutput",
    "ConceptDiagnosisSkill",
    "Misconception",
    "get_concept_diagnosis_skill",
]
