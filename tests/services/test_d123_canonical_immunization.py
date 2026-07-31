"""D-123 — تحصين الاحتمالات بالمحتوى الرسمي (history-immune): لا LLM، لا تلوّث.

الكارثة (screenshots + transcript حي): نص LLM مُهلوَس في الـ history («2 برتقالية +
3 زرقاء») سمّم استخراج التركيبة ⇒ كاروسيل خاطئ («سحب 2 من 11» + «كرة زرقاء» غير
موجودة). حين يعجز الاستخراج عن إيجاد التركيبة في نافذة الـ history ⇒ None ⇒ سقوط
لمسار LLM السقراطي (حلقة «كم عدد الكرات؟» + هلوسة).

D-123: محادثة التمرين الاحتمالي تُبنى من **المحتوى الرسمي المُفهرَس** + نية السؤال،
بـ `history=None` ⇒ مناعة كاملة من تلوّث الـ history ⇒ الكاروسيل الصحيح دائماً
(2بيضاء/4حمراء/5خضراء) ⇒ terminate=True ⇒ صفر LLM.

stdlib + source-inspection — يعمل في الـ sandbox بلا pydantic.
"""

from __future__ import annotations

from pathlib import Path

# D-164: `_build_calculated_ui`/`_build_probability_tree_props` live in the ProbabilityUIMixin
# now; read the full tutor source (client + brain + mixins) via the single manifest.
# (stdlib-only import — pydantic-free, still runs in the sandbox.)
from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_SRC = read_tutor_source()
# نطاق دالة _build_calculated_ui (نتأكّد أن الإصلاح داخلها لا في مكان آخر).
_BUILD_UI = CLIENT_SRC[CLIENT_SRC.index("def _build_calculated_ui(") :]
_BUILD_UI = _BUILD_UI[: _BUILD_UI.index("\n    async def _build_probability_tree_props")]


# ── 1. المحتوى الرسمي موجود (التركيبة قابلة للاستخراج) ─────────────────────────
class TestOfficialContent:
    def test_indexed_2024_has_composition(self) -> None:
        f = REPO_ROOT / "knowledge_base/bac2024_math_experimental_subject1_ex1_ex2.md"
        assert f.is_file()
        src = f.read_text(encoding="utf-8")
        assert "كرتان بيضاوان" in src
        assert "أربع كرات حمراء" in src
        assert "خمس كرات خضراء" in src


# ── 2. التحصين موصول في _build_calculated_ui (history-immune) ──────────────────
class TestImmunizationWiring:
    def test_step1_inline_question_alone_no_history(self) -> None:
        # الخطوة 1: السؤال وحده (history=None) — يلتقط التركيبة inline بلا تلوّث.
        assert (
            "result = skill.analyze(ProbabilityInput(question=question, history=None))" in _BUILD_UI
        )

    def test_step2_canonical_resolution_is_delegated_not_inlined(self) -> None:
        """D-191: الخطوة 2 صارت نداءً للمُحلّ الواحد بدل حقن النصّ الرسمي هنا.

        D-137 (assert the invariant, not the line): كان هذا الاختبار يؤكّد وجود
        ``ProbabilityInput(question=f"{_official} {question}")`` حرفياً — أي أنه
        كان يحرس **آليةً** لا **قاعدة**. وتلك الآلية نفسها كانت الخطأ: حقن نصّ
        التمرين المرجعي يجعل أرقامه تفوز بالاستخراج فيرى الطالبُ كيساً ليس كيسَه
        (ISS-140 د). القاعدة الباقية هي مناعة D-123: الاستخراج لا يُبنى على
        history مُلوَّث — وهي الآن مسؤولية ``exercise_context``.
        """
        assert "resolve_exercise_context(question, history_messages)" in _BUILD_UI
        # والآلية القديمة ممنوعة من العودة.
        assert 'ProbabilityInput(question=f"{_official} {question}", history=None)' not in _BUILD_UI

    def test_step2_gated_by_probability_context(self) -> None:
        assert "not _result_ok(result) and _is_probability_context(_combined_text)" in _BUILD_UI

    def test_step3_last_resort_after_immunization(self) -> None:
        # الترتيب هو العقد: inline (بلا history) → المُحلّ الواحد → آخر ملاذ بالـ history.
        pos1 = _BUILD_UI.index("question=question, history=None")
        pos2 = _BUILD_UI.index("resolve_exercise_context(question, history_messages)")
        pos3 = _BUILD_UI.index("question=question, history=history_messages")
        assert pos1 < pos2 < pos3, "order must be: inline → resolver → last-resort"

    def test_is_probability_context_defined_before_first_analyze(self) -> None:
        def_pos = _BUILD_UI.index("def _is_probability_context(")
        analyze_pos = _BUILD_UI.index("question=question, history=None")
        assert def_pos < analyze_pos

    def test_single_probability_context_definition(self) -> None:
        # لا تكرار تعريف (D-122 dedup).
        assert _BUILD_UI.count("def _is_probability_context(") == 1


# ── 3. منطق الحراس (standalone) ────────────────────────────────────────────────
class TestGuards:
    def test_is_probability_context_logic(self) -> None:
        def ctx(text):
            return any(
                m in (text or "")
                for m in ("كرات", "كرة", "كيس", "احتمال", "سحب", "نسحب", "p(a", "p(b")
            )

        assert ctx("يحتوي كيس على 11 كرة ... نسحب 3 كرات") is True
        assert ctx("ادرس تغيّرات الدالة f(x)") is False
        assert ctx("") is False

    def test_result_ok_semantics(self) -> None:
        # _result_ok: None أو success=False ⇒ غير صالح (يُجرَّب الملاذ التالي).
        class _R:
            def __init__(self, success=True):
                self.success = success

        def result_ok(r):
            return r is not None and getattr(r, "success", True) is not False

        assert result_ok(None) is False
        assert result_ok(_R(success=False)) is False
        assert result_ok(_R(success=True)) is True
        assert result_ok(object()) is True  # لا حقل success ⇒ صالح


# ── 4. مبدأ المناعة: history=None يُسقط نص الـ history المُهلوَس ────────────────
class TestContaminationImmunity:
    def test_canonical_uses_history_none_not_messages(self) -> None:
        """مناعة D-123: استخراج التركيبة لا يرى history مُلوَّثاً — أينما سكن.

        D-137: الآلية انتقلت إلى ``exercise_context`` (D-191)، فالقاعدة تُؤكَّد على
        المُحلّ نفسه: كل نداء ``analyze`` فيه يمرّر ``history=None``. هلوسة المساعد
        في الـ history («2 برتقالية + 3 زرقاء») هي ما سمّم التركيبة أصلاً.
        """
        resolver = (REPO_ROOT / "app/services/skills/exercise_context.py").read_text(
            encoding="utf-8"
        )
        assert "ProbabilityInput(question=candidate_text, history=None)" in resolver
        # ولا يوجد في المُحلّ أيّ تمرير لـ history إلى المحرّك.
        assert "history=history_messages" not in resolver
