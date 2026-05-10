"""اختبارات ChatRoutingPolicy — الخطوة الانتقالية الثانية (D-021).

يتحقق من:
  - الوضع الافتراضي يوجّه نحو /api/chat/messages (StateGraph)
  - وضع التراجع يوجّه نحو /agent/chat (OrchestratorAgent)
  - القيم غير المعروفة تُعيد إلى الوضع الافتراضي
  - targets_state_graph يعكس الوضع الصحيح
  - وضع الطوارئ (breakglass) يدعم عناوين متعددة
"""

from __future__ import annotations

import pytest

from app.infrastructure.clients.routing_policy import (
    _ENDPOINT_MAP,
    ChatRoutingPolicy,
)

BASE = "http://orchestrator-service:8006"


class TestDefaultMode:
    """الوضع الافتراضي يجب أن يوجّه نحو StateGraph."""

    def test_default_targets_state_graph_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """بدون متغير بيئي، يجب أن تكون نقطة النهاية /api/chat/messages."""
        monkeypatch.delenv("ORCHESTRATOR_CHAT_ENDPOINT", raising=False)
        policy = ChatRoutingPolicy.from_environment(BASE)
        urls = policy.candidate_urls()
        assert len(urls) == 1
        assert urls[0] == f"{BASE}/api/chat/messages"

    def test_default_targets_state_graph_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """targets_state_graph يجب أن يكون True في الوضع الافتراضي."""
        monkeypatch.delenv("ORCHESTRATOR_CHAT_ENDPOINT", raising=False)
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.targets_state_graph is True

    def test_explicit_state_graph_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ORCHESTRATOR_CHAT_ENDPOINT=state_graph يجب أن يوجّه نحو /api/chat/messages."""
        monkeypatch.setenv("ORCHESTRATOR_CHAT_ENDPOINT", "state_graph")
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.candidate_urls() == [f"{BASE}/api/chat/messages"]
        assert policy.targets_state_graph is True


class TestRollbackMode:
    """وضع التراجع يجب أن يوجّه نحو OrchestratorAgent."""

    def test_agent_mode_targets_agent_chat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ORCHESTRATOR_CHAT_ENDPOINT=agent يجب أن يوجّه نحو /agent/chat."""
        monkeypatch.setenv("ORCHESTRATOR_CHAT_ENDPOINT", "agent")
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.candidate_urls() == [f"{BASE}/agent/chat"]
        assert policy.targets_state_graph is False

    def test_agent_mode_endpoint_mode_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """endpoint_mode يجب أن يكون 'agent' في وضع التراجع."""
        monkeypatch.setenv("ORCHESTRATOR_CHAT_ENDPOINT", "agent")
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.endpoint_mode == "agent"


class TestUnknownMode:
    """القيم غير المعروفة يجب أن تُعيد إلى الوضع الافتراضي."""

    def test_unknown_mode_falls_back_to_state_graph(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """قيمة غير معروفة تُعيد إلى state_graph مع تحذير."""
        monkeypatch.setenv("ORCHESTRATOR_CHAT_ENDPOINT", "invalid_mode_xyz")
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.endpoint_mode == "state_graph"
        assert policy.targets_state_graph is True

    def test_empty_string_falls_back_to_state_graph(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """قيمة فارغة تُعيد إلى state_graph."""
        monkeypatch.setenv("ORCHESTRATOR_CHAT_ENDPOINT", "")
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.endpoint_mode == "state_graph"


class TestBreakglassMode:
    """وضع الطوارئ يدعم عناوين متعددة."""

    def test_breakglass_adds_fallback_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ORCHESTRATOR_ALLOW_MULTI_TARGET_CHAT=1 يضيف عناوين احتياطية."""
        monkeypatch.setenv("ORCHESTRATOR_ALLOW_MULTI_TARGET_CHAT", "1")
        monkeypatch.setenv(
            "ORCHESTRATOR_SERVICE_FALLBACK_URLS",
            "http://orchestrator-b:8006,http://orchestrator-c:8006",
        )
        monkeypatch.delenv("ORCHESTRATOR_CHAT_ENDPOINT", raising=False)
        policy = ChatRoutingPolicy.from_environment(BASE)
        urls = policy.candidate_urls()
        assert len(urls) == 3
        assert all("/api/chat/messages" in u for u in urls)

    def test_breakglass_deduplicates_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """العناوين المكررة تُزال."""
        monkeypatch.setenv("ORCHESTRATOR_ALLOW_MULTI_TARGET_CHAT", "1")
        monkeypatch.setenv("ORCHESTRATOR_SERVICE_FALLBACK_URLS", BASE)
        monkeypatch.delenv("ORCHESTRATOR_CHAT_ENDPOINT", raising=False)
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert len(policy.candidate_urls()) == 1


class TestEndpointMap:
    """_ENDPOINT_MAP يجب أن يحتوي على القيم الصحيحة."""

    def test_state_graph_path(self) -> None:
        assert _ENDPOINT_MAP["state_graph"] == "/api/chat/messages"

    def test_agent_path(self) -> None:
        assert _ENDPOINT_MAP["agent"] == "/agent/chat"

    def test_no_extra_modes(self) -> None:
        """لا يجب إضافة أوضاع جديدة بدون ADR."""
        assert set(_ENDPOINT_MAP.keys()) == {"state_graph", "agent"}


class TestFallbackAndContractVersion:
    """الـ fallback وإصدار العقد يجب أن يُقرآ من البيئة."""

    def test_fallback_enabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ORCHESTRATOR_LOCAL_FALLBACK_ENABLED", raising=False)
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.fallback_enabled is True

    def test_fallback_disabled_by_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORCHESTRATOR_LOCAL_FALLBACK_ENABLED", "0")
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.fallback_enabled is False

    def test_contract_version_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CHAT_CONTRACT_VERSION", raising=False)
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.contract_version == "v1"

    def test_contract_version_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CHAT_CONTRACT_VERSION", "v2")
        policy = ChatRoutingPolicy.from_environment(BASE)
        assert policy.contract_version == "v2"
