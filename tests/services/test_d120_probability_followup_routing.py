"""D-120 — متابعات P(A)/P(B)/P(C)/E(X) تُوجَّه للبصري الحتمي (لا LLM، لا تسرّب).

الكارثة (transcript حي): «كيف اتعلم حساب الحادثة P(A)» (بلا «احتمال») تسقط لمسار
LLM سقراطي يسأل «كم العدد الكلي؟» مع تسرّب إنجليزي («لنبدأ با determination»). السبب:
`_has_followup_probability_intent` يطابق عبر `_normalize` الذي **لا يُحوِّل لأحرف
صغيرة**، فـ `"p("` لا يطابق `P(A)` (حرف كبير) ⇒ تفشل بوّابة D-101 ⇒ LLM.

D-120: المطابقة case-insensitive (مرآة `_detect_focus_step`). يُختبَر هنا منطق
الكاشف standalone (sandbox-safe — لا pydantic) + source-inspection للإصلاح.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_SRC = (REPO_ROOT / "app/services/skills/probability_skill.py").read_text(encoding="utf-8")

# تطبيع مطابق لـ ProbabilityCalculatorSkill._normalize (sandbox-safe replica).
_TASHKEEL_RE = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ࣓-ࣿ]")


def _normalize(text: str) -> str:
    if not text:
        return ""
    cleaned = _TASHKEEL_RE.sub("", text)
    return cleaned.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")


# مرآة _FOLLOWUP_PROBABILITY_INTENT (يجب أن تبقى متّسقة مع المصدر).
_FOLLOWUP = (
    "p(",
    "p_a",
    "نفس اللون",
    "same color",
    "فردي",
    "زوجي",
    "شرطي",
    "جداء",
    "الامل",
    "الأمل",
    "امل رياضي",
    "متغير عشوائي",
    "المتغير",
    "e(x",
    "x>1",
    "فضاء",
    "تأليف",
    "تاليف",
)


def _has_followup_d120(text: str) -> bool:
    """D-120: case-insensitive — يطابق سلوك `_has_followup_probability_intent` بعد الإصلاح."""
    normalized = _normalize(text).lower()
    return any(_normalize(m).lower() in normalized for m in _FOLLOWUP)


def _has_followup_old(text: str) -> bool:
    """قبل D-120 (بلا lower) — يُثبت الكارثة."""
    normalized = _normalize(text)
    return any(_normalize(m) in normalized for m in _FOLLOWUP)


# ── 1. الإصلاح: متابعات الاحتمال بحرف كبير تُطابَق الآن ─────────────────────────
class TestFollowupCaseInsensitive:
    def test_uppercase_event_refs_now_match(self) -> None:
        for q in (
            "كيف اتعلم حساب الحادثة P(A)",  # الكارثة الحرفية (بلا «احتمال»)
            "احسب P(B)",
            "استنتج P(C)",
            "احسب P(X>1)",
            "احسب الأمل الرياضي E(X)",
        ):
            assert _has_followup_d120(q), f"D-120: must route to visual: {q!r}"

    def test_catastrophe_was_real_before_fix(self) -> None:
        # قبل D-120، «الحادثة P(A)» (بلا «احتمال») لم تُطابق ⇒ سقطت لـ LLM.
        assert _has_followup_old("كيف اتعلم حساب الحادثة P(A)") is False
        assert _has_followup_d120("كيف اتعلم حساب الحادثة P(A)") is True

    def test_non_probability_still_rejected(self) -> None:
        # لا false-positive: سؤال غير احتمالي لا يُطابق (حاجب تبديل الموضوع D-101).
        for q in ("اشرح قانون نيوتن", "ما هو التكامل بالتجزئة", "عرّف الدالة الأصلية"):
            assert _has_followup_d120(q) is False, f"false positive: {q!r}"


# ── 2. source-inspection: الإصلاح مطبَّق فعلاً في المصدر ───────────────────────
class TestSourceFix:
    def test_followup_intent_lowercases(self) -> None:
        start = SKILL_SRC.index("def _has_followup_probability_intent")
        seg = SKILL_SRC[start : start + 900]  # window يتجاوز الـ docstring متعدّد الأسطر
        # كلا الطرفين يُحوَّل لأحرف صغيرة.
        assert "_normalize(text).lower()" in seg
        assert "_normalize(m).lower()" in seg

    def test_visual_request_lowercases(self) -> None:
        start = SKILL_SRC.index("def is_visual_request")
        seg = SKILL_SRC[start : start + 700]
        assert "_normalize(text).lower()" in seg

    def test_followup_markers_unchanged(self) -> None:
        # قائمة المتابعة لا تزال تغطّي رموز الخطوات (مرآة _detect_focus_step).
        for marker in ('"p("', '"e(x"', '"المتغير"', '"الأمل"', '"نفس اللون"'):
            assert marker in SKILL_SRC, f"follow-up marker dropped: {marker}"
