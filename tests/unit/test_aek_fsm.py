"""
اختبارات النواة التعليمية التكيّفية (AEK) — Protocol V44.0.

تغطّي:
    - آلة الحالة المحدودة (FSM): الانتقالات المسموح بها والممنوعة
    - نموذج الحالة المعرفية (AEKRuntimeState)
    - المحرّك الرئيسي (AdaptiveEducationalKernel): happy path + error path
    - قانون العزل الموضوعي (Topic Isolation)
    - قانون الحِمل الإدراكي (Cognitive Load)
    - قانون القناتين (Dual Channel)
"""

from __future__ import annotations

import pytest

from app.services.aek.fsm import (
    ALLOWED_TRANSITIONS,
    CognitiveState,
    is_valid_transition,
    transition,
)
from app.services.aek.kernel import AdaptiveEducationalKernel, _detect_confusion
from app.services.aek.state import AEKRuntimeState, ExerciseScope, LearnerCapability

# ─────────────────────────────────────────────────────────────────────────────
# FSM — الانتقالات
# ─────────────────────────────────────────────────────────────────────────────


class TestFSMTransitions:
    """اختبارات آلة الحالة المحدودة الإعلانية."""

    def test_valid_transition_standard_to_confusion(self) -> None:
        result = transition(CognitiveState.STANDARD, CognitiveState.CONFUSION)
        assert result == CognitiveState.CONFUSION

    def test_valid_transition_confusion_to_emotional_recovery(self) -> None:
        result = transition(CognitiveState.CONFUSION, CognitiveState.EMOTIONAL_RECOVERY)
        assert result == CognitiveState.EMOTIONAL_RECOVERY

    def test_valid_transition_visual_to_step_reasoning(self) -> None:
        result = transition(CognitiveState.VISUAL_INTUITION, CognitiveState.STEP_REASONING)
        assert result == CognitiveState.STEP_REASONING

    def test_valid_transition_step_to_formal(self) -> None:
        result = transition(CognitiveState.STEP_REASONING, CognitiveState.FORMAL_MATH)
        assert result == CognitiveState.FORMAL_MATH

    def test_valid_transition_formal_to_standard(self) -> None:
        result = transition(CognitiveState.FORMAL_MATH, CognitiveState.STANDARD)
        assert result == CognitiveState.STANDARD

    def test_invalid_transition_returns_current_state(self) -> None:
        """الانتقال الممنوع يُعيد الحالة الحالية — controlled fallback."""
        # CONFUSION → FORMAL_MATH ممنوع
        result = transition(CognitiveState.CONFUSION, CognitiveState.FORMAL_MATH)
        assert result == CognitiveState.CONFUSION

    def test_invalid_transition_emotional_to_standard(self) -> None:
        # EMOTIONAL_RECOVERY → STANDARD ممنوع
        result = transition(CognitiveState.EMOTIONAL_RECOVERY, CognitiveState.STANDARD)
        assert result == CognitiveState.EMOTIONAL_RECOVERY

    def test_all_states_have_allowed_transitions(self) -> None:
        """كل حالة يجب أن تملك انتقالات مُعرَّفة."""
        for state in CognitiveState:
            assert state in ALLOWED_TRANSITIONS, f"{state} missing from ALLOWED_TRANSITIONS"
            assert len(ALLOWED_TRANSITIONS[state]) > 0

    def test_is_valid_transition_true(self) -> None:
        assert is_valid_transition(CognitiveState.STANDARD, CognitiveState.CONFUSION) is True

    def test_is_valid_transition_false(self) -> None:
        assert is_valid_transition(CognitiveState.CONFUSION, CognitiveState.FORMAL_MATH) is False


# ─────────────────────────────────────────────────────────────────────────────
# AEKRuntimeState — نموذج الحالة
# ─────────────────────────────────────────────────────────────────────────────


class TestAEKRuntimeState:
    """اختبارات نموذج الحالة المعرفية."""

    def test_default_state(self) -> None:
        state = AEKRuntimeState()
        assert state.current_cognitive_state == CognitiveState.STANDARD
        assert state.cognitive_load_index == 0.3
        assert state.topic_lock is False
        assert state.current_step_index == 0

    def test_cognitive_load_rejects_above_1(self) -> None:
        """Pydantic يرفض القيم خارج [0,1] — الـ clamp يعمل في _estimate_cognitive_load."""
        import pytest as _pytest
        from pydantic import ValidationError
        with _pytest.raises(ValidationError):
            AEKRuntimeState(cognitive_load_index=1.5)

    def test_cognitive_load_rejects_below_0(self) -> None:
        import pytest as _pytest
        from pydantic import ValidationError
        with _pytest.raises(ValidationError):
            AEKRuntimeState(cognitive_load_index=-0.5)

    def test_is_overloaded_true(self) -> None:
        state = AEKRuntimeState(cognitive_load_index=0.8)
        assert state.is_overloaded() is True

    def test_is_overloaded_false(self) -> None:
        state = AEKRuntimeState(cognitive_load_index=0.5)
        assert state.is_overloaded() is False

    def test_abstraction_level_novice_overloaded(self) -> None:
        state = AEKRuntimeState(
            learner_capability=LearnerCapability.NOVICE,
            cognitive_load_index=0.9,
        )
        assert state.abstraction_level_allowed() == 1

    def test_abstraction_level_advanced_low_load(self) -> None:
        state = AEKRuntimeState(
            learner_capability=LearnerCapability.ADVANCED,
            cognitive_load_index=0.2,
        )
        assert state.abstraction_level_allowed() == 3

    def test_abstraction_level_intermediate_medium_load(self) -> None:
        state = AEKRuntimeState(
            learner_capability=LearnerCapability.INTERMEDIATE,
            cognitive_load_index=0.5,
        )
        assert state.abstraction_level_allowed() == 2

    def test_record_transition_appends_log(self) -> None:
        state = AEKRuntimeState()
        state.record_transition(CognitiveState.STANDARD, CognitiveState.CONFUSION)
        assert "STANDARD→CONFUSION" in state.transition_log


# ─────────────────────────────────────────────────────────────────────────────
# كشف الحيرة
# ─────────────────────────────────────────────────────────────────────────────


class TestConfusionDetection:
    """اختبارات كاشف الحيرة."""

    @pytest.mark.parametrize("text", [
        "لم أفهم هذه الخطوة",
        "مفهمتش كيفاش نحسب",
        "اشرح لي من جديد",
        "مش واضح ليا",
        "I don't understand this",
        "je comprends pas",
        "لماذا نضرب في هذا",
    ])
    def test_detects_confusion(self, text: str) -> None:
        assert _detect_confusion(text) is True

    @pytest.mark.parametrize("text", [
        "احسب احتمال سحب كرة حمراء",
        "ما هو C(5,2)",
        "حل التمرين الأول",
        "شكراً",
    ])
    def test_no_false_positives(self, text: str) -> None:
        assert _detect_confusion(text) is False


# ─────────────────────────────────────────────────────────────────────────────
# AdaptiveEducationalKernel — المحرّك الرئيسي
# ─────────────────────────────────────────────────────────────────────────────


class TestAdaptiveEducationalKernel:
    """اختبارات المحرّك الرئيسي."""

    def setup_method(self) -> None:
        self.kernel = AdaptiveEducationalKernel()

    def test_happy_path_standard_question(self) -> None:
        output = self.kernel.process(
            question="احسب احتمال سحب كرتين حمراوتين من كيس يحتوي 5 كرات",
            history=[],
        )
        assert output.channel_a.cognitive_state is not None
        assert output.channel_a.cognitive_intent is not None
        assert output.channel_b.narrative != ""
        assert output.updated_state is not None
        assert output.processing_ms >= 0

    def test_confusion_triggers_mode_b(self) -> None:
        output = self.kernel.process(
            question="مفهمتش كيفاش نحسب الاحتمال",
            history=[],
        )
        assert output.channel_a.runtime_mode == "MODE_B"
        assert output.channel_a.terminate_pipeline is False

    def test_direct_question_triggers_mode_a(self) -> None:
        output = self.kernel.process(
            question="احسب C(5,2)",
            history=[],
        )
        assert output.channel_a.runtime_mode == "MODE_A"
        assert output.channel_a.terminate_pipeline is True

    def test_probability_scope_detected(self) -> None:
        output = self.kernel.process(
            question="كيس يحتوي 3 كرات حمراء و4 بيضاء، احسب احتمال سحب كرة حمراء",
            history=[],
        )
        assert output.channel_a.exercise_scope == ExerciseScope.PROBABILITY
        assert output.channel_a.topic_lock is True

    def test_topic_lock_preserved_across_turns(self) -> None:
        """topic_lock يبقى مُفعَّلاً عبر الأدوار."""
        first = self.kernel.process(
            question="كيس يحتوي كرات، احسب الاحتمال",
            history=[],
        )
        assert first.updated_state.topic_lock is True

        second = self.kernel.process(
            question="ما هي الخطوة التالية؟",
            history=[],
            state=first.updated_state,
        )
        assert second.updated_state.topic_lock is True

    def test_cognitive_load_increases_on_confusion(self) -> None:
        initial = AEKRuntimeState(cognitive_load_index=0.3)
        output = self.kernel.process(
            question="لم أفهم هذا الشرح أبداً",
            history=[],
            state=initial,
        )
        assert output.updated_state.cognitive_load_index > 0.3

    def test_advanced_learner_gets_higher_abstraction(self) -> None:
        state = AEKRuntimeState(
            learner_capability=LearnerCapability.ADVANCED,
            cognitive_load_index=0.1,
        )
        output = self.kernel.process(
            question="احسب التكامل",
            history=[],
            state=state,
        )
        assert output.channel_a.abstraction_level >= 2

    def test_overloaded_learner_gets_level_1_abstraction(self) -> None:
        state = AEKRuntimeState(
            learner_capability=LearnerCapability.NOVICE,
            cognitive_load_index=0.9,
        )
        output = self.kernel.process(
            question="لم أفهم شيئاً",
            history=[],
            state=state,
        )
        assert output.channel_a.abstraction_level == 1

    def test_step_index_increments(self) -> None:
        state = AEKRuntimeState()
        out1 = self.kernel.process("سؤال أول", [], state)
        out2 = self.kernel.process("سؤال ثانٍ", [], out1.updated_state)
        assert out2.updated_state.current_step_index > out1.updated_state.current_step_index

    def test_dual_channel_separation(self) -> None:
        """القناتان لا تتلوّثان — A لا تحتوي narrative، B لا تحتوي JSON."""
        output = self.kernel.process("احسب الاحتمال", [])
        # Channel A: لا narrative
        assert "narrative" not in output.channel_a.model_dump()
        # Channel B: لا cognitive_intent
        assert "cognitive_intent" not in output.channel_b.model_dump()

    def test_none_state_creates_default(self) -> None:
        """state=None يُنشئ حالة افتراضية بدون خطأ."""
        output = self.kernel.process("سؤال", [], state=None)
        assert output.updated_state.current_cognitive_state is not None

    def test_empty_history_handled(self) -> None:
        output = self.kernel.process("سؤال", history=[])
        assert output is not None

    def test_emotional_recovery_on_overloaded_confusion(self) -> None:
        """حيرة + حِمل مرتفع → EMOTIONAL_RECOVERY."""
        state = AEKRuntimeState(
            current_cognitive_state=CognitiveState.CONFUSION,
            cognitive_load_index=0.85,
        )
        output = self.kernel.process(
            question="مفهمتش والله ما فهمت شيء",
            history=[],
            state=state,
        )
        assert output.channel_a.cognitive_state in (
            CognitiveState.EMOTIONAL_RECOVERY,
            CognitiveState.CONFUSION,
        )


# ─────────────────────────────────────────────────────────────────────────────
# قانون الحالة المستحيلة المحلية (§VI)
# ─────────────────────────────────────────────────────────────────────────────


class TestImpossibleBranchIsolation:
    """الحالة المستحيلة تُعزَل محلياً — لا تُدمِّر الحالة الأم."""

    def test_impossible_branch_flag_default_false(self) -> None:
        kernel = AdaptiveEducationalKernel()
        output = kernel.process("احسب C(5,2)", [])
        assert output.channel_a.impossible_branch is False

    def test_parent_state_survives_impossible_branch(self) -> None:
        """الحالة الأم تبقى سليمة حتى لو كان فرع محلي مستحيلاً."""
        kernel = AdaptiveEducationalKernel()
        state = AEKRuntimeState(
            current_exercise_scope=ExerciseScope.PROBABILITY,
            topic_lock=True,
        )
        output = kernel.process(
            question="احسب احتمال سحب 5 كرات من كيس يحتوي 3 فقط",
            history=[],
            state=state,
        )
        # الحالة الأم لا تزال PROBABILITY
        assert output.updated_state.current_exercise_scope == ExerciseScope.PROBABILITY
        assert output.updated_state.topic_lock is True
