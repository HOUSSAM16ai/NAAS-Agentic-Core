"""
D-133 — حالة الطالب كإشارة قرار (النيّة + الإحباط) regression tests.

يثبت إعادة توجيه المالك ونقده الثلاثي:
  • النيّة تُحدّد نوع الرد لا الكلمة: «لم أفهم X»⇒confusion (+secondary definition)، «أعطني مثالاً»
    ⇒example_request، «كيف نحسب»⇒procedure، «ما الفرق»⇒comparison، «ما معنى»⇒definition.
  • متعدّد-إشارات (نقد 1): primary + secondary، لا تصنيف جامد.
  • LLM = مُفسِّر ثانوي لا حَكَم (نقد 2): يُستدعى فقط عند primary=unknown ولا يطغى على الحتمي.
  • الإحباط لحظي يتلاشى (نقد 3): تصعيد 0→high ثم تعافٍ على رسالة غير-حيرة؛ لا تخزين.
  • إشارة قرار: frustration=high ⇒ budget=0 ⇒ symbolic_reveal؛ كل intent ⇒ response_mode مغاير.
  • فحص بنيوي: التوصيل في orchestrator_client + PolicyInput + الـ gate.
"""

from __future__ import annotations

from pathlib import Path

from app.services.skills.pedagogical_policy_skill import (
    PolicyInput,
    get_pedagogical_policy_skill,
    response_mode_for,
    socratic_budget,
)
from app.services.skills.student_state_skill import (
    StudentStateInput,
    get_student_state_skill,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def _read(question: str, history=None):
    return get_student_state_skill().read(StudentStateInput(question=question, history=history))


# ── النيّة الأساسية (deterministic) ──────────────────────────────────────────
class TestIntentClassification:
    def test_confusion_about_concept_carries_definition_secondary(self) -> None:
        # وصفة المالك الحرفية: «لم أفهم X» = confusion + (definition) — لا تعريف-فقط.
        st = _read("لم أفهم المتغير العشوائي")
        assert st.primary_intent == "confusion"
        assert "definition" in st.secondary_signals  # نقد 1: متعدّد-إشارات

    def test_example_request(self) -> None:
        assert _read("أعطني مثالاً على المتغير العشوائي").primary_intent == "example_request"

    def test_procedure(self) -> None:
        assert _read("كيف نحسب الأمل الرياضي").primary_intent == "procedure"
        assert _read("ما هي الخطوات").primary_intent == "procedure"

    def test_comparison(self) -> None:
        assert _read("ما الفرق بين البسط والمقام").primary_intent == "comparison"

    def test_definition(self) -> None:
        assert _read("ما معنى المتغير العشوائي").primary_intent == "definition"
        assert _read("ماذا نقصد بالحادثة A").primary_intent == "definition"

    def test_hint_request(self) -> None:
        assert _read("اعطني تلميح").primary_intent == "hint_request"

    def test_answer_to_pending_socratic(self) -> None:
        history = [{"role": "assistant", "content": "ما عدد الكرات الحمراء؟"}]
        assert _read("أربعة", history).primary_intent == "answer"

    def test_short_answer_without_pending_is_not_answer(self) -> None:
        # لا سؤال معلّق ⇒ ليست «إجابة».
        assert _read("نفس اللون", None).primary_intent != "answer"

    def test_confusion_overrides(self) -> None:
        # الحيرة تطغى (لحظة تدخّل): «لم أفهم، أعطني مثالاً» ⇒ primary=confusion.
        st = _read("لم أفهم، أعطني مثالاً")
        assert st.primary_intent == "confusion"
        assert "example_request" in st.secondary_signals

    def test_unknown_for_plain_request(self) -> None:
        assert _read("اعطني تمرين").primary_intent == "unknown"

    def test_fail_open_on_garbage(self) -> None:
        assert _read("؟؟؟").primary_intent in ("unknown", "confusion")
        assert _read(".").primary_intent == "unknown"


# ── الإحباط لحظي يتلاشى (نقد 3) ──────────────────────────────────────────────
class TestTransientFrustration:
    def _hist(self, *msgs: str):
        return [{"role": "user", "content": m} for m in msgs]

    def test_escalation_to_high(self) -> None:
        h = self._hist("لم أفهم", "لم أفهم", "لم أفهم")
        assert _read("لم أفهم", h).frustration == "high"

    def test_medium(self) -> None:
        h = self._hist("لم أفهم")
        assert _read("لم أفهم", h).frustration == "medium"

    def test_low_single(self) -> None:
        assert _read("لم أفهم", None).frustration == "low"

    def test_none_when_no_confusion(self) -> None:
        assert _read("ما هو المتغير العشوائي", None).frustration == "none"

    def test_decay_on_recovery(self) -> None:
        # نقد 3: مهما تراكمت الحيرة سابقاً، رسالة غير-حيرة حالية ⇒ تعافٍ (لا high).
        h = self._hist("لم أفهم", "لم أفهم", "لم أفهم", "لم أفهم")
        recovered = _read("شكراً، فهمت الآن", h)
        assert recovered.frustration in ("none", "low")
        assert recovered.frustration != "high"


# ── إشارة قرار: السياسة تتغيّر فعلاً (لا labels فقط) ──────────────────────────
class TestDecisionSignal:
    def test_high_frustration_zeros_budget(self) -> None:
        assert socratic_budget("event_meaning", support_level=4, frustration="high") == 0
        # بدون إحباط: ميزانية طبيعية.
        assert socratic_budget("event_meaning", support_level=4, frustration="none") >= 1

    def test_high_frustration_forces_symbolic_reveal(self) -> None:
        out = get_pedagogical_policy_skill().decide(
            PolicyInput(
                concept="event_meaning",
                question="لم أفهم",
                history=[{"role": "assistant", "content": "سؤال؟"}],
                intent="confusion",
                frustration="high",
            )
        )
        assert out.action == "symbolic_reveal"
        assert out.response_mode == "reveal"

    def test_response_mode_per_intent(self) -> None:
        # كل intent ⇒ نوع رد مغاير (الـ label يُنتج بيداغوجيا، لا تصنيفاً).
        assert response_mode_for("confusion", "definition", None) == "confusion_enriched"
        assert response_mode_for("example_request", "definition", None) == "example_first"
        assert response_mode_for("procedure", "socratic", None) == "steps"
        assert response_mode_for("comparison", "definition", None) == "relationship"
        assert response_mode_for("definition", "definition", None) == "define"
        assert response_mode_for("hint_request", "socratic", None) == "hint"
        # الإحباط يطغى دائماً.
        assert response_mode_for("definition", "definition", "high") == "reveal"

    def test_policy_records_without_crash(self) -> None:
        out = get_pedagogical_policy_skill().decide(
            PolicyInput(
                concept="numerator",
                question="ما معنى البسط",
                intent="definition",
                frustration="none",
            )
        )
        assert out.response_mode == "define"


# ── فحص بنيوي: التوصيل (لا ZOMBIE) + نقد 2 (LLM لا يطغى) ──────────────────────
class TestWiring:
    def _client(self) -> str:
        return (ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
            encoding="utf-8"
        )

    def test_skill_consumed_in_client(self) -> None:
        src = self._client()
        assert "get_student_state_skill" in src
        assert "intent=_state.primary_intent" in src
        assert "frustration=_state.frustration" in src

    def test_confusion_enriched_in_preempt(self) -> None:
        src = self._client()
        # الحيرة ⇒ تعريف + مثال (balls) + سؤال موجِّه (وصفة المالك).
        assert "_build_concrete_example" in src
        assert "_generate_guiding_question" in src
        assert "confusion_enriched" in src

    def test_llm_secondary_does_not_override(self) -> None:
        skill = (ROOT / "app/services/skills/student_state_skill.py").read_text(encoding="utf-8")
        # نقد 2: الـ LLM يُستدعى فقط عند primary=unknown.
        assert 'primary_intent != "unknown"' in skill
        assert "read_or_classify" in skill

    def test_frustration_not_persisted(self) -> None:
        skill = (ROOT / "app/services/skills/student_state_skill.py").read_text(encoding="utf-8")
        for forbidden in ("async_session", "session_factory", "INSERT", "commit("):
            assert forbidden not in skill  # نقد 3: لحظي لا يُخزَّن

    def test_manifest_entry(self) -> None:
        from app.services.skills.doctrine import (
            SKILL_DOCTRINE_MANIFEST,
            STUDENT_STATE_DOCTRINE,
            STUDENT_STATE_DOCTRINE_VERSION,
        )

        entry = SKILL_DOCTRINE_MANIFEST["student_state"]
        assert entry["version"] == STUDENT_STATE_DOCTRINE_VERSION
        assert entry["rules_count"] == len(STUDENT_STATE_DOCTRINE)
