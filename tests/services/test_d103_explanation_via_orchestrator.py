"""D-103 — اختبارات الـ monolith: تمرير شرح التمارين عبر orchestrator.

نمط source-inspection (مثل test_iss110): يحرس بنية التوجيه في
``OrchestratorClient.chat_with_agent`` ضد أي refactor يكسر:
1. حقن ``exercise_content`` بدل البثّ المحلي عند تفعيل العلم.
2. رافعة الرجوع ``EXPLANATION_VIA_ORCHESTRATOR=0``.
3. حارس البثّ الفارغ (orchestrator 200 بلا محتوى ⇒ fallback).
4. تمرير القرار المحسوب مسبقاً إلى fallback tier 2.5 (ISS-059 parity).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_SRC = (REPO_ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
    encoding="utf-8"
)


class TestExplanationRoutingStructure:
    def test_flag_helper_exists_with_default_on(self):
        assert "_explanation_via_orchestrator_enabled" in CLIENT_SRC
        assert 'os.getenv("EXPLANATION_VIA_ORCHESTRATOR", "1")' in CLIENT_SRC

    def test_tier25_injects_instead_of_streaming_when_enabled(self):
        """عند العلم المفعَّل: لا بثّ محلي — حقن exercise_content والمتابعة للـ orchestrator."""
        assert "_exercise_injection" in CLIENT_SRC
        assert '"exercise_content": _exp_full_content' in CLIENT_SRC
        assert '"exercise_ref"' in CLIENT_SRC
        # سطر log التوجيه الكاشف
        assert "explanation_via_orchestrator file=" in CLIENT_SRC

    def test_payload_context_carries_injection(self):
        assert "**_exercise_injection" in CLIENT_SRC, (
            "payload context must spread _exercise_injection (exercise_content/exercise_ref)"
        )

    def test_local_path_preserved_as_else_branch(self):
        """السلوك المحلي القديم يبقى كاملاً (العلم معطَّل / لا محتوى)."""
        # كتلة البثّ المحلي المسبق لا تزال موجودة مع precomputed_decision
        assert CLIENT_SRC.count("precomputed_decision=") >= 2, (
            "both the preempt branch and the fallback tier must pass precomputed_decision"
        )
        assert 'fallback_path": 0.75' in CLIENT_SRC.replace("'", '"')

    def test_empty_stream_guard_present(self):
        """orchestrator 200 بلا أي محتوى مرئي ولا terminal ⇒ يُعامل كفشل."""
        assert "_orch_visible" in CLIENT_SRC
        assert "empty_stream" in CLIENT_SRC
        assert "chat_routing_empty_stream" in CLIENT_SRC
        # الإرجاع مشروط بالرؤية — لا return غير مشروط بعد حلقة البثّ
        guard_pos = CLIENT_SRC.index("if _orch_visible:")
        ret_pos = CLIENT_SRC.index("return", guard_pos)
        assert ret_pos - guard_pos < 120

    def test_terminal_events_mark_visible(self):
        """أي إطار نهائي يحفظ عقد الإطار الواحد — لا fallback بعد terminal."""
        seg_start = CLIENT_SRC.index("_orch_visible = False")
        seg_end = CLIENT_SRC.index("chat_routing_empty_stream")
        seg = CLIENT_SRC[seg_start:seg_end]
        for terminal in ('"assistant_final"', '"assistant_error"', '"error"', '"complete"'):
            assert terminal in seg, f"terminal type {terminal} must mark the stream visible"

    def test_fallback_tier25_reuses_precomputed_decision(self):
        """fallback chain tier 2.5 لا يعيد الكشف — يستخدم _explanation_decision من الأعلى."""
        # موضع fallback tier 2.5 (بعد محاولة الـ orchestrator)
        fb_marker = "orchestrator.fallback.exercise_explanation.stream"
        fb_pos = CLIENT_SRC.index(fb_marker)
        fb_segment = CLIENT_SRC[fb_pos : fb_pos + 2500]
        assert "_explanation_decision" in fb_segment, (
            "fallback tier 2.5 must pass the precomputed decision (ISS-059 parity)"
        )


class TestFlagParsing:
    def test_flag_parsing_semantics(self, monkeypatch):
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        fn = OrchestratorClient._explanation_via_orchestrator_enabled
        monkeypatch.delenv("EXPLANATION_VIA_ORCHESTRATOR", raising=False)
        assert fn() is True, "default must be ON (user chose more-via-LangGraph)"
        for off in ("0", "false", "False", "NO", " no "):
            monkeypatch.setenv("EXPLANATION_VIA_ORCHESTRATOR", off)
            assert fn() is False, f"{off!r} must disable"
        for on in ("1", "true", "yes", "anything"):
            monkeypatch.setenv("EXPLANATION_VIA_ORCHESTRATOR", on)
            assert fn() is True, f"{on!r} must keep it enabled"


class TestRoutingOrderInvariants:
    """ثوابت الترتيب — مرآة ISS-110/ISS-111 مع D-103."""

    def test_indexed_match_still_precedes_explanation(self):
        """الاسترجاع المُفهرَس (نص حرفي بدون LLM) يسبق كشف الشرح دائماً (D-101)."""
        indexed_pos = CLIENT_SRC.index("_has_indexed_match(")
        explanation_pos = CLIENT_SRC.index("detect_explanation_with_context(")
        assert indexed_pos < explanation_pos

    def test_explanation_detection_precedes_orchestrator_payload(self):
        """القرار يُحسب قبل بناء الـ payload حتى يُحقن في context."""
        decision_pos = CLIENT_SRC.index("_explanation_decision = detect_explanation_with_context")
        payload_pos = CLIENT_SRC.index('"routing_mode": "MODE_B" if _is_mode_b else "MODE_A"')
        assert decision_pos < payload_pos
