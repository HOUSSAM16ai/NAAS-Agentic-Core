"""ISS-131 (D-169) — كارثتان مكتشفتان حياً في E2E الكامل (D-168 Stage E):

1. **تسميم سلك HTTP بـ PolicyDecision (D-144-era)**: `chat_with_agent` كان يحقن
   `context["policy_decision"] = <dataclass>` ثم ينشر الـ context كاملاً في جسم
   POST نحو الـ orchestrator ⇒ `TypeError: Object of type PolicyDecision is not
   JSON serializable` ⇒ فشل **كل** المرشّحين ⇒ `ORCHESTRATOR_REQUIRED` (إطار خطأ)
   للأسئلة العامة في محادثة جديدة. والأدهى: لا أحد كان يقرأ الحقن أصلاً —
   `customer_chat.record_turn` يقرأ من `tutor_state_ctx` لا من الـ context الأعلى.

2. **اختطاف قناة الإدمن بالـ probe (D-159-era، خرق قاعدة D-102)**: بوّابة سياق
   الاحتمالات في `_cognitive_turn` (و `_history_text` في chat_turn) كانت تمسح
   **كل** رسائل الـ history بما فيها رسالة system — وبرومبت الإدمن (21K حرف)
   يحوي «كرة/احتمال» ⇒ كل سؤال إدمن يُصنَّف «سياق احتمالات» ويُختطف بالـ probe
   («كم عدد ملفات بايثون؟» ⇒ «لنبدأ من فهمك أنت — نسحب 3 كرات...»).

قاعدة D-102 (المحفورة في CLAUDE.md §6.89): «رسائل system لا تدخل أي كاشف history».
"""

from __future__ import annotations

import json

import pytest

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source
from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.skills.pedagogical_policy_engine import PolicyDecision

# ─── سيناريو الكارثة الحرفي (transcript الإدمن الحي 2026-07-16) ───────────────
_ADMIN_SYSTEM_PROMPT_SNIPPET = (
    "أنت مساعد إداري خارق. عند شرح الاحتمالات استخدم أمثلة مثل سحب كرة من كيس. "
    "احرص على دقة كل احتمال تعرضه."
)
_ADMIN_QUESTION = "كم عدد ملفات بايثون في المشروع؟"


class TestWireContextSanitization:
    """Fix 1 — القرار الداخلي لا يركب السلك أبداً."""

    def test_policy_decision_and_tutor_state_stripped(self):
        ctx = {
            "chat_scope": "customer",
            "policy_decision": PolicyDecision(
                next_action="socratic",
                learning_stage="definition",
                representation="text",
                focus=None,
                reason="test",
            ),
            "tutor_state": {"kc_progress": {}, "policy_decision": object()},
            "support_level": 3,
            "session_id": "s1",
        }
        wire = OrchestratorClient._sanitize_wire_context(ctx)
        assert "policy_decision" not in wire
        assert "tutor_state" not in wire
        assert wire["support_level"] == 3
        assert wire["session_id"] == "s1"
        # الجوهر: الجسم الصالح للسلك قابل للتسلسل JSON — كان يرمي TypeError.
        json.dumps(wire)

    def test_none_and_non_dict_context_safe(self):
        assert OrchestratorClient._sanitize_wire_context(None) == {}
        assert OrchestratorClient._sanitize_wire_context("garbage") == {}  # type: ignore[arg-type]

    def test_original_context_not_mutated(self):
        ctx = {"policy_decision": object(), "keep": 1}
        OrchestratorClient._sanitize_wire_context(ctx)
        assert "policy_decision" in ctx  # نسخة — الأصل (handoff الداخلي) يبقى

    def test_payload_build_uses_sanitizer_and_injection_targets_tutor_state(self):
        """source-guard: البناء يستدعي المُطهِّر، والحقن صار في tutor_state المشترك."""
        src = read_tutor_source()
        assert "**self._sanitize_wire_context(context)" in src
        assert 'tutor_state["policy_decision"] = policy_decision' in src
        # الحقن القديم المسموم (D-144) يجب ألا يعود أبداً.
        assert 'context["policy_decision"] = policy_decision' not in src


class TestSystemPromptNeverEntersHistoryDetectors:
    """Fix 2 — قاعدة D-102: رسائل system لا تدخل كواشف الـ history."""

    def test_cognitive_turn_ignores_system_only_probability_context(self):
        """سيناريو الإدمن الحرفي: سياق احتمالي في system فقط ⇒ لا اختطاف."""
        history = [
            {"role": "system", "content": _ADMIN_SYSTEM_PROMPT_SNIPPET},
            {"role": "user", "content": _ADMIN_QUESTION},
        ]
        text, delta = OrchestratorClient._cognitive_turn(_ADMIN_QUESTION, history, {})
        assert text is None and delta is None

    def test_cognitive_turn_still_fires_on_real_user_probability_context(self):
        """ضابط إيجابي: سياق احتمالي حقيقي من رسائل الطالب يبقى يعمل."""
        history = [
            {
                "role": "user",
                "content": "اعطني تمرين الاحتمالات 2024",
            },
            {
                "role": "assistant",
                "content": (
                    "يحتوي كيس على إحدى عشرة كرة: أربع كرات حمراء وخمس كرات خضراء "
                    "وكرتان بيضاوان. نسحب عشوائياً وفي آن واحد ثلاث كرات."
                ),
            },
        ]
        text, _delta = OrchestratorClient._cognitive_turn("كيف احل السؤال الأول", history, {})
        assert text is not None and len(text) > 20

    def test_calculated_ui_ignores_system_only_probability_context(self):
        """الموقع الثالث: `_build_calculated_ui` لا يبني خطوة تركيز من برومبت system.

        قبل الإصلاح: نفس سيناريو الإدمن أنتج companion «سنشرح الآن خطوة الحدث
        المطلوب فقط...» لأن الكاشف قرأ «كرة/احتمال» من رسالة system.
        """
        history = [
            {"role": "system", "content": _ADMIN_SYSTEM_PROMPT_SNIPPET},
            {"role": "user", "content": _ADMIN_QUESTION},
        ]
        assert OrchestratorClient._build_calculated_ui(_ADMIN_QUESTION, history) is None

    def test_role_filter_present_in_both_gates(self):
        """source-guard: الكواشف (turn_engine + chat_turn + probability_ui) تُرشِّح الدور."""
        src = read_tutor_source()
        assert src.count('m.get("role") in ("user", "assistant")') >= 3


class TestAdminConversationIdNeverCrossesNamespace:
    """Fix 4 — معرّف محادثة الإدمن (جدول admin_conversations) لا يعبر الحدود.

    الـ orchestrator يتحقق من الملكية ضد فضاء محادثات العميل ⇒ تمرير معرّف
    الإدمن كان يُرجِع 403 لكل دور إدمن يصل السلك (ISS-019 family).
    """

    def test_admin_scope_strips_conversation_id_from_wire(self):
        src = read_tutor_source()
        assert '"conversation_id": _wire_conversation_id' in src
        assert 'context.get("chat_scope") == "admin"' in src

    def test_service_jwt_carries_admin_claim_for_admin_scope(self):
        """Fix 5 — درس D-162/§6.78 على service JWT: بدون claim الإدمن، الـ
        orchestrator (fail-closed `_is_admin_payload`) يرفض أدوات الإدمن بـ
        `ADMIN_ACCESS_DENIED` رغم نجاح تنفيذ الأداة (سيناريو «كم عدد ملفات بايثون»)."""
        import jwt as pyjwt

        client = OrchestratorClient()
        admin_token = client._build_service_jwt(3, is_admin=True)
        claims = pyjwt.decode(admin_token, options={"verify_signature": False})
        assert claims["is_admin"] is True
        assert claims["role"] == "admin"
        # القناة العادية لا تحمل أي claim إداري (مبدأ أقل صلاحية).
        user_token = client._build_service_jwt(7)
        user_claims = pyjwt.decode(user_token, options={"verify_signature": False})
        assert "is_admin" not in user_claims and "role" not in user_claims


class TestPolicyDecisionHandoffReachesConsumer:
    """Fix 3 — الحقن يصل للمستهلك الفعلي (tutor_state المشترك ⇒ record_turn)."""

    @pytest.mark.asyncio
    async def test_shared_tutor_state_receives_decision(self, monkeypatch):
        """chat_with_agent يكتب القرار في نفس dict الذي مرّره المُنادي."""
        monkeypatch.setenv("REQUIRE_ORCHESTRATOR", "0")
        client = OrchestratorClient()
        shared_tutor_state: dict[str, object] = {}
        ctx: dict[str, object] = {"chat_scope": "customer", "tutor_state": shared_tutor_state}
        agen = client.chat_with_agent(
            question="السلام عليكم",  # تحية ⇒ fastpath ⇒ لا حاجة لأي خدمة خارجية
            user_id=1,
            conversation_id=None,
            history_messages=[],
            context=ctx,
        )
        async for _event in agen:
            break  # أول حدث يكفي — الحقن يحدث قبل أي preempt
        await agen.aclose()
        assert isinstance(shared_tutor_state.get("policy_decision"), PolicyDecision)
