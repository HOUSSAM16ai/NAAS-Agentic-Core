from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

"""
ISS-120 (D-153) — Canonical-loader poisoning + confusion-as-answer + unguarded repetition.

The live transcript catastrophe (BAC-2024 probability):
1. «بطاقة رقم 0 (العدد 3)» phantom group + C(14,3)=364 — the symbolic engine was fed the
   FULL official file (statement + worked solution); solution prose «…لا تحمل الرقم 0 …
   سحب 3 كرات» matched the numbered-entity markers → n=14 instead of 11/165.
2. D-152's validation gate never fired: its regex only saw bare `N/M` fractions while the
   official file writes every denominator as LaTeX `\\frac{56}{165}`.
3. «لم أفهم» was treated as a CORRECT answer («إجابتك في الطريق الصحيح —») because
   `is_response_to_socratic` accepted bare confusion and `_heuristic_understood` returned
   True for any non-empty text.
4. The understanding-state emit path bypassed `_recently_emitted` → verbatim repetition
   of «تخيّل أنك سحبت 3 كرات…» on every «لم أفهم».
"""

from app.services.capabilities.exercise_retrieval import (
    _trim_at_solution,
    load_exercise_questions_only,
)
from app.services.skills.pedagogical_policy_skill import (
    _is_bare_confusion as policy_bare_confusion,
)
from app.services.skills.pedagogical_policy_skill import (
    is_response_to_socratic,
)
from app.services.skills.probability_skill import (
    CombinationsModelOutput,
    ProbabilityCalculatorSkill,
    ProbabilityInput,
)
from app.services.skills.socratic_evaluator_skill import _heuristic_understood

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OFFICIAL_MD = _REPO_ROOT / "knowledge_base" / "bac2024_math_experimental_subject1_ex1_ex2.md"

# سؤال سقراطي معلّق (أحدث رسالة مساعد تنتهي بسؤال قصير) — سياق احتمالات.
_SOCRATIC_HISTORY = [
    {"role": "user", "content": "اعطني تمرين الاحتمالات 2024 — كيس فيه كرات"},
    {"role": "assistant", "content": "متى تقول إن الحادثة A تحقّقت؟ أعطني مثالاً"},
]


class TestPhantomEntityKilled:
    """Fix B: نثر الحل لا يولِّد كياناً وهمياً — التركيبة المختلطة تُسقِط المرقّمة."""

    def test_full_official_content_yields_colors_only(self):
        content = _OFFICIAL_MD.read_text(encoding="utf-8")
        entities = ProbabilityCalculatorSkill._extract_count_entities(content)
        labels = [e[0] for e in entities]
        assert not any("رقم" in lb for lb in labels), labels
        assert sum(e[2] for e in entities) == 11

    def test_full_official_content_analyzes_to_11_165(self):
        content = _OFFICIAL_MD.read_text(encoding="utf-8")
        result = ProbabilityCalculatorSkill().analyze(
            ProbabilityInput(question=content, history=None)
        )
        assert isinstance(result, CombinationsModelOutput)
        assert result.n == 11
        assert result.total_combinations == 165
        assert result.same_group_favorable == 14

    def test_card_only_exercise_unaffected(self):
        # D-076: تمارين البطاقات النقية (بلا كيانات لون) تبقى تعمل.
        text = "كيس فيه 8 بطاقات، منها 3 بطاقات تحمل الرقم 1. نسحب بطاقة عشوائياً"
        entities = ProbabilityCalculatorSkill._extract_count_entities(text)
        assert any("رقم 1" in e[0] for e in entities), entities

    def test_questions_only_loader_strips_solution(self):
        content = _OFFICIAL_MD.read_text(encoding="utf-8")
        trimmed = _trim_at_solution(content)
        assert len(trimmed) < len(content)
        assert "الرقم 0" not in trimmed or "وعددها 3 كرات" not in trimmed


class TestLatexAwareGate:
    """Fix C: بوّابة D-152 تقرأ كسور LaTeX \\frac إضافةً للصيغة الخام N/M."""

    def test_latex_frac_denominator_parsed(self):
        denoms = ProbabilityCalculatorSkill._stated_denominators(
            r"علماً أن $$P(B) = \frac{56}{165}$$ و $P(X=0)=\dfrac{56}{165}$"
        )
        assert 165 in denoms

    def test_bare_slash_still_parsed(self):
        denoms = ProbabilityCalculatorSkill._stated_denominators("النتيجة 14/165 كما في الحل")
        assert 165 in denoms

    def test_poisoned_composition_rejected(self):
        # تركيبة مسمومة (14 عنصراً ⇒ C(14,3)=364) مع مقام مُصرَّح 165 بصيغة LaTeX.
        poisoned = (
            "يحتوي كيس على 14 كرة: أربع كرات حمراء و كرتان بيضاوان و خمس كرات خضراء "
            "و بطاقة رقم 0 وعددها 3 كرات. نسحب 3 كرات دفعة واحدة. "
            r"علماً أن P(B) = \frac{56}{165}"
        )
        result = ProbabilityCalculatorSkill().analyze(
            ProbabilityInput(question=poisoned, history=None)
        )
        if isinstance(result, CombinationsModelOutput):
            total = result.total_combinations
            assert total % 165 == 0 or 165 % total == 0, total


class TestConfusionIsNeverAnAnswer:
    """Fix E: «لم أفهم» حيرة تُوجَّه لمسارات الحيرة — ليست إجابة ولا فهماً."""

    @pytest.mark.parametrize(
        "msg",
        ["لم أفهم", "لم افهم التمرين", "مفهمتش", "ما فهمت والو", "لا أفهم"],
    )
    def test_bare_confusion_is_not_a_socratic_response(self, msg):
        assert is_response_to_socratic(msg, _SOCRATIC_HISTORY) is False

    def test_real_answers_still_accepted(self):
        assert is_response_to_socratic("نفس اللون", _SOCRATIC_HISTORY) is True
        genius = "إذا كانوا من نفس اللون فقط و هذا ينطبق على الحمراء و الخضراء فقط"
        assert is_response_to_socratic(genius, _SOCRATIC_HISTORY) is True

    def test_long_substantive_confusion_stays_evaluable(self):
        # حيرة تحمل محتوى فعلياً (> 6 كلمات) تُترَك للمُقيّم يزنها كاملة.
        msg = "لم أفهم لماذا نجمع الحالات الممكنة في هذا السؤال بالذات هنا"
        assert policy_bare_confusion(msg) is False

    @pytest.mark.parametrize("msg", ["لم أفهم", "مفهمتش", "ما فهمتش"])
    def test_heuristic_understood_rejects_bare_confusion(self, msg):
        for concept in ("combinations", "denominator", "full_solution"):
            assert _heuristic_understood(msg, concept) is False

    def test_heuristic_understood_keeps_substantive_attempts(self):
        assert _heuristic_understood("نستعمل التوافيق لأن الترتيب لا يهم", "combinations") is True

    @pytest.mark.asyncio
    async def test_evaluate_bare_confusion_deterministic_false(self):
        from app.services.skills.socratic_evaluator_skill import (
            SocraticEvaluatorInput,
            SocraticEvaluatorSkill,
        )

        out = await SocraticEvaluatorSkill().evaluate(
            SocraticEvaluatorInput(
                student_answer="لم أفهم",
                concept="combinations",
                facts="",
                history=[],
                verified_correct=False,
            )
        )
        assert out.understood is False
        assert out.source == "fallback"  # لا استدعاء LLM للحيرة المجرّدة


class TestSourceWiring:
    """Source-inspection: الأسلاك الدائمة لقواعد D-153 (تحرسها أيضاً بوّابة CI)."""

    def _orch_src(self) -> str:
        # D-164: عقل الاحتمالات + بُناته موزّعة على brain + mixins — نقرأ المصدر الكامل
        # عبر المانيفست (`load_exercise_questions_only` تنتقل مع `_build_calculated_ui`).
        from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

        return read_tutor_source()

    def test_canonical_loaders_use_questions_only(self):
        """القاعدة: **لا مسار استخراج يقرأ نثر الحلّ النموذجي** — الملف الكامل لمرجع RAG وحده.

        D-137 (assert the invariant, not the line): كان هنا عدّ (``>= 6``) يقيس
        **عدد النسخ** لا القاعدة. وD-191 وحّد مواضع الاسترجاع في مُحلٍّ واحد، فهبط
        العدّ بينما القاعدة صارت **أقوى** (موضع واحد يستحيل أن يتفرّق). العدّ كان
        يُعاقب التوحيد — فنؤكّد القاعدة نفسها بدله.
        """
        from pathlib import Path

        src = self._orch_src()
        # مسار الاستخراج **الوحيد** (D-191) لا يلمس الملف الكامل إطلاقاً.
        resolver = (
            Path(__file__).resolve().parents[2] / "app/services/skills/exercise_context.py"
        ).read_text(encoding="utf-8")
        assert "load_exercise_questions_only(" in resolver
        assert "load_exercise_content(" not in resolver, (
            "نثر الحلّ النموذجي ممنوع على مسار استخراج الكيانات (ISS-120)"
        )
        # ويبقى الملف الكامل مقروءاً خارج الاستخراج فقط (مرجع RAG — D-145).
        assert "load_exercise_content(_decision.matched_entry)" in src

    def test_rag_reference_keeps_full_content(self):
        # D-145: مرجع الـ RAG-Grounded LLM يبقى الملف الكامل (الحل النموذجي مقصود هناك).
        src = self._orch_src()
        assert "load_exercise_content(_decision.matched_entry)" in src

    def test_understanding_state_emit_path_has_repetition_guard(self):
        src = self._orch_src()
        block = src.split("حارس التكرار على مسار محرّك حالة الفهم", 1)
        assert len(block) == 2, "ISS-120 repetition guard comment missing"
        tail = block[1][:2600]
        # ISS-121 (D-154): الحارس صار سلسلة بدائل عبر `_d153_dup` (تستدعي
        # `_recently_emitted` داخلياً) — لا بثّ مكرَّر بنيوياً.
        assert "_d153_dup(_direct)" in tail
        assert "last_step_emitted" in tail

    def test_explain_count_counts_representation_snippets(self):
        from app.services.skills import understanding_state_skill

        src = inspect.getsource(understanding_state_skill.UnderstandingStateSkill._explain_count)
        assert "rep_snippets" in src

    def test_no_string_inert_in_frontend_component(self):
        jsx = (_REPO_ROOT / "frontend" / "app" / "components" / "CogniForgeApp.jsx").read_text(
            encoding="utf-8"
        )
        assert not re.search(r"inert=\{[^}]*\?\s*[\"']true[\"']", jsx)
        assert "inert={!isAgentSidebarOpen || undefined}" in jsx
        assert "inert={!isSidebarOpen || undefined}" in jsx


class TestQuestionsOnlyLoaderFunctional:
    """load_exercise_questions_only يقطع الحل ويُبقي التركيبة والترقيم (D-143 parity)."""

    def test_loader_yields_correct_combo_and_parity(self):
        from app.services.capabilities.exercise_retrieval import (
            ExerciseRetrievalRequest,
            detect_exercise_retrieval,
        )

        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024")
        )
        assert decision.recognized and decision.matched_entry
        qonly = load_exercise_questions_only(decision.matched_entry)
        assert qonly
        result = ProbabilityCalculatorSkill().analyze(
            ProbabilityInput(question=qonly, history=None)
        )
        assert isinstance(result, CombinationsModelOutput)
        assert (result.n, result.total_combinations) == (11, 165)
        parity = ProbabilityCalculatorSkill.number_parity_counts(qonly)
        assert parity == {"odd": 8, "even": 3, "zero": 2, "total": 11}
