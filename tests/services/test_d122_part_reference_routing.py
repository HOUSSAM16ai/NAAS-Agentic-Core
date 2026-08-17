"""D-122 — إشارات أجزاء التمرين الطبيعية ⇒ البصري الحتمي (لا نص LLM).

الكارثة (transcript حي): «كيف احل السؤال الأول» (إشارة طبيعية للسؤال 1 = P(A)) لا
تحوي رمز `P(A)` ولا `نفس اللون` ⇒ لا تُتعرَّف كخطوة الحدث ⇒ تسقط لمسار LLM السقراطي
العام («حدّد المطلوب... قسّم النجاحات...» + عربية مكسورة «كلزيادة»). المالك يريد:
أي إشارة للسؤال 1/P(A)/الحدث A ⇒ تفصيل الحدث الملموس (أبيض مستحيل/أحمر 4/أخضر 10 → 14/165).

D-122: `_detect_part_reference` يربط الإشارات الطبيعية بخطوة الحدث، **محروساً بسياق
الاحتمالات** (history) كي لا تُحمَّل احتمالات في محادثة موضوع آخر (topic-safe).

stdlib + source-inspection — يعمل في الـ sandbox بلا pydantic.
"""

from __future__ import annotations

from pathlib import Path

# D-164: `_build_calculated_ui` (+ its inner `_detect_part_reference`/`_is_probability_context`
# helpers) live in the ProbabilityUIMixin now; read the full tutor source via the manifest.
from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_SRC = read_tutor_source()


# نسخة standalone مطابقة لمنطق D-122 (sandbox-safe replica).
def _detect_part_reference(user_question: str) -> str | None:
    q = user_question.lower()
    if "السؤال الثاني" in q or "السؤال 2" in q or "السوال الثاني" in q or "الجزء الثاني" in q:
        return "random_variable"
    if any(
        m in q
        for m in (
            "السؤال الاول",
            "السؤال الأول",
            "السؤال 1",
            "السوال الاول",
            "الجزء الاول",
            "الجزء الأول",
            "الجزء 1",
            "الحدث a",
            "الحادثة a",
            "حل السؤال",
            "حل السوال",
        )
    ):
        return "same_color_event"
    return None


def _is_probability_context(text: str) -> bool:
    return any(
        m in (text or "") for m in ("كرات", "كرة", "كيس", "احتمال", "سحب", "نسحب", "p(a", "p(b")
    )


_PROB_HIST = "يحتوي كيس على 11 كرة موزعة ... نسحب عشوائيًا 3 كرات دفعة واحدة"
_FUNC_HIST = "ادرس تغيّرات الدالة f(x)=x^2-1 على المجال المعطى"


# ── 1. الإشارات الطبيعية تُربَط بالخطوة الصحيحة (ضمن سياق احتمالات) ────────────
class TestPartReferenceMapping:
    def test_first_question_maps_to_event(self) -> None:
        for q in (
            "كيف احل السؤال الأول",
            "كيف احل السؤال الاول",
            "اشرح الجزء الأول",
            "ما حل الحدث A",
            "حل السؤال 1",
        ):
            combined = f"{q} {_PROB_HIST}"
            assert _is_probability_context(combined)
            assert _detect_part_reference(q) == "same_color_event", q

    def test_second_question_maps_to_random_variable(self) -> None:
        for q in ("احسب السؤال الثاني", "اشرح الجزء الثاني", "السؤال 2"):
            assert _detect_part_reference(q) == "random_variable", q


# ── 2. topic-safe: لا تحميل احتمالات في موضوع آخر ─────────────────────────────
class TestTopicSafety:
    def test_part_reference_gated_by_probability_context(self) -> None:
        # «السؤال الأول» في محادثة دوال ⇒ لا سياق احتمالات ⇒ لا تُربَط (آمن).
        combined = f"كيف احل السؤال الأول {_FUNC_HIST}"
        assert _is_probability_context(combined) is False
        # الكود الفعلي يطبّق _detect_part_reference فقط حين _is_probability_context.

    def test_probability_context_detection(self) -> None:
        assert _is_probability_context(_PROB_HIST) is True
        assert _is_probability_context(_FUNC_HIST) is False
        assert _is_probability_context("") is False


# ── 3. source-inspection: التطبيق المحروس مطبَّق فعلاً ─────────────────────────
class TestSourceWiring:
    def test_helpers_defined(self) -> None:
        assert "def _detect_part_reference(" in CLIENT_SRC
        assert "def _is_probability_context(" in CLIENT_SRC

    def test_guarded_application_present(self) -> None:
        # يُطبَّق فقط حين focus صريح مفقود + سياق احتمالات مؤكَّد.
        assert "_focus_step_id is None and _is_probability_context(_combined_text)" in CLIENT_SRC
        assert "_focus_step_id = _detect_part_reference(question)" in CLIENT_SRC

    def test_confusion_default_to_event(self) -> None:
        # «لم أفهم» في سياق احتمالات بلا جزء محدّد ⇒ خطوة الحدث.
        assert "if _focus_step_id is None and _is_deep_pedagogy:" in CLIENT_SRC
        assert '_focus_step_id = "same_color_event"' in CLIENT_SRC

    def test_topic_guard_precedes(self) -> None:
        # حاجب تبديل الموضوع (D-101) يبقى قبل منطق الإشارات الطبيعية.
        #
        # D-266 (ISS-159): كان هذا الفحص يبحث عن حرفية الحارس القديم
        # `_canonical.canonical_id != "probability"` — وهي الصيغة التي **لا تعمل**
        # لسؤال فيزياء (سجلّ الاسترجاع يصمت فيسقط الشرط عند ساقه الأولى). فكان
        # الاختبار يحرس **وجود الحارس** لا **عمله**. المُسنَد الواحد يستبدلها،
        # والقاعدة المحروسة هي نفسها: الموضوع يُحسم قبل منطق الإشارات.
        guard_pos = CLIENT_SRC.index("is_foreign_to_probability(question)")
        partref_pos = CLIENT_SRC.index("def _detect_part_reference(")
        assert guard_pos < partref_pos, "D-101 topic guard must precede D-122 part-ref logic."
