"""
اختبارات D-045 — End-to-End User Routing via Microservices.

تتحقق من:
  - ChatRoutingPolicy تُوجِّه إلى state_graph افتراضياً
  - OrchestratorClient يُولِّد JWT داخلي صحيح
  - supervisor.sh يضبط المتغيرات البيئية الصحيحة
  - orchestrator /api/chat/messages يقبل question + auth
  - WebSocket يدعم jwt subprotocol
  - pipeline_mode field موجود في /compose response
  - كل خدمة تملك prometheus-client في requirements.txt
"""

from __future__ import annotations

import pathlib
from typing import ClassVar

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _ci_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """يضبط متغيرات بيئة CI آمنة لكل اختبار."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-ci-pipeline-secure-length")
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("LLM_MOCK_MODE", "1")
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.setenv("ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR", "true")
    monkeypatch.setenv("ORCHESTRATOR_SERVICE_URL", "http://localhost:8006")
    monkeypatch.setenv("ORCHESTRATOR_CHAT_ENDPOINT", "state_graph")


# ── 1. ChatRoutingPolicy Tests ────────────────────────────────────────────────


class TestChatRoutingPolicy:
    """يتحقق من سياسة التوجيه الافتراضية والبديلة."""

    def test_defaults_to_state_graph(self) -> None:
        """الوضع الافتراضي يجب أن يكون state_graph → /api/chat/messages."""
        from app.infrastructure.clients.routing_policy import ChatRoutingPolicy

        policy = ChatRoutingPolicy.from_environment("http://localhost:8006")
        assert policy.targets_state_graph is True
        assert policy.endpoint_mode == "state_graph"

    def test_state_graph_url_is_correct(self) -> None:
        """state_graph يجب أن يُوجِّه إلى /api/chat/messages."""
        from app.infrastructure.clients.routing_policy import ChatRoutingPolicy

        policy = ChatRoutingPolicy.from_environment("http://localhost:8006")
        urls = policy.candidate_urls()
        assert len(urls) == 1
        assert urls[0] == "http://localhost:8006/api/chat/messages"

    def test_agent_mode_rollback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ORCHESTRATOR_CHAT_ENDPOINT=agent يُوجِّه إلى /agent/chat."""
        monkeypatch.setenv("ORCHESTRATOR_CHAT_ENDPOINT", "agent")
        from importlib import reload

        import app.infrastructure.clients.routing_policy as rp

        reload(rp)

        policy = rp.ChatRoutingPolicy.from_environment("http://localhost:8006")
        assert policy.targets_state_graph is False
        assert "/agent/chat" in policy.candidate_urls()[0]

    def test_unknown_mode_falls_back_to_state_graph(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """قيمة غير معروفة تعود إلى state_graph مع تحذير."""
        monkeypatch.setenv("ORCHESTRATOR_CHAT_ENDPOINT", "invalid_mode")
        from importlib import reload

        import app.infrastructure.clients.routing_policy as rp

        reload(rp)

        policy = rp.ChatRoutingPolicy.from_environment("http://localhost:8006")
        assert policy.targets_state_graph is True

    def test_fallback_enabled_by_default(self) -> None:
        """fallback_enabled يجب أن يكون True افتراضياً."""
        from app.infrastructure.clients.routing_policy import ChatRoutingPolicy

        policy = ChatRoutingPolicy.from_environment("http://localhost:8006")
        assert policy.fallback_enabled is True

    def test_contract_version_default(self) -> None:
        """contract_version يجب أن يكون v1 افتراضياً."""
        from app.infrastructure.clients.routing_policy import ChatRoutingPolicy

        policy = ChatRoutingPolicy.from_environment("http://localhost:8006")
        assert policy.contract_version == "v1"


# ── 2. Supervisor Configuration Tests ─────────────────────────────────────────


class TestSupervisorConfig:
    """يتحقق من أن supervisor.sh يضبط المتغيرات الصحيحة."""

    SUPERVISOR = pathlib.Path(".devcontainer/supervisor.sh")

    def _read(self) -> str:
        return self.SUPERVISOR.read_text()

    def test_supervisor_exists(self) -> None:
        assert self.SUPERVISOR.exists(), "supervisor.sh not found"

    def test_sets_orchestrator_service_url(self) -> None:
        assert "ORCHESTRATOR_SERVICE_URL" in self._read()
        assert "localhost:8006" in self._read()

    def test_sets_codespaces_true(self) -> None:
        src = self._read()
        assert 'CODESPACES="true"' in src or "CODESPACES=true" in src

    def test_sets_allow_container_localhost(self) -> None:
        src = self._read()
        assert "ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR" in src
        assert "true" in src

    def test_sets_orchestrator_chat_endpoint(self) -> None:
        assert "ORCHESTRATOR_CHAT_ENDPOINT" in self._read()

    def test_sets_microservice_urls(self) -> None:
        src = self._read()
        for url_var in [
            "PLANNING_AGENT_URL",
            "RESEARCH_AGENT_URL",
            "REASONING_AGENT_URL",
            "USER_SERVICE_URL",
        ]:
            assert url_var in src, f"supervisor.sh missing {url_var}"

    def test_launches_all_services(self) -> None:
        src = self._read()
        for launcher in [
            "launch_orchestrator_service",
            "launch_user_service",
            "launch_planning_agent",
            "launch_research_agent",
            "launch_reasoning_agent",
            "launch_content_retrieval_skill",
            "launch_conversation_service",
        ]:
            assert launcher in src, f"supervisor.sh missing {launcher}"

    def test_asyncpg_url_conversion(self) -> None:
        """supervisor.sh يجب أن يحوِّل postgresql:// إلى postgresql+asyncpg://."""
        src = self._read()
        assert "postgresql+asyncpg" in src or "asyncpg" in src


# ── 3. WebSocket Protocol Tests ───────────────────────────────────────────────


class TestWebSocketProtocol:
    """يتحقق من دعم jwt subprotocol في WebSocket."""

    def test_ws_auth_supports_jwt_subprotocol(self) -> None:
        src = pathlib.Path("app/api/routers/ws_auth.py").read_text()
        assert '"jwt"' in src or "'jwt'" in src

    def test_ws_auth_extracts_token_from_subprotocol(self) -> None:
        src = pathlib.Path("app/api/routers/ws_auth.py").read_text()
        assert "protocols" in src

    def test_customer_chat_uses_orchestrator_client(self) -> None:
        src = pathlib.Path("app/api/routers/customer_chat.py").read_text()
        assert "orchestrator_client" in src
        assert "chat_with_agent" in src

    def test_customer_chat_has_websocket_endpoint(self) -> None:
        src = pathlib.Path("app/api/routers/customer_chat.py").read_text()
        assert "@router.websocket" in src

    def test_customer_chat_streams_to_user(self) -> None:
        src = pathlib.Path("app/api/routers/customer_chat.py").read_text()
        assert "stream_and_forward" in src
        assert "websocket.send_json" in src


# ── 4. Orchestrator Chat Endpoint Tests ───────────────────────────────────────


class TestOrchestratorChatEndpoint:
    """يتحقق من عقد /api/chat/messages في orchestrator."""

    ROUTES = pathlib.Path("microservices/orchestrator_service/src/api/routes.py")

    def _read(self) -> str:
        return self.ROUTES.read_text()

    def test_has_api_chat_messages_post(self) -> None:
        assert '@router.post("/api/chat/messages"' in self._read()

    def test_has_agent_chat_fallback(self) -> None:
        assert '@router.post("/agent/chat"' in self._read()

    def test_has_websocket_endpoint(self) -> None:
        assert '@router.websocket("/api/chat/ws")' in self._read()

    def test_extract_chat_objective_handles_question(self) -> None:
        src = self._read()
        start = src.find("def _extract_chat_objective")
        assert start != -1
        func = src[start : start + 400]
        assert "question" in func

    def test_extract_chat_objective_handles_objective(self) -> None:
        src = self._read()
        start = src.find("def _extract_chat_objective")
        func = src[start : start + 400]
        assert "objective" in func

    def test_returns_streaming_response(self) -> None:
        assert "StreamingResponse" in self._read()

    def test_emits_conversation_init_event(self) -> None:
        assert "conversation_init" in self._read()

    def test_emits_assistant_final_event(self) -> None:
        assert "assistant_final" in self._read()

    def test_requires_jwt_auth(self) -> None:
        assert "_decode_auth_payload_or_401" in self._read()


# ── 5. Skills Pipeline Contract Tests ─────────────────────────────────────────


class TestSkillsPipelineContract:
    """يتحقق من عقد /compose وحقول pipeline_mode."""

    PIPELINE = pathlib.Path("microservices/orchestrator_service/src/services/skills_pipeline.py")

    def _read(self) -> str:
        return self.PIPELINE.read_text()

    def test_pipeline_file_exists(self) -> None:
        assert self.PIPELINE.exists()

    def test_has_pipeline_mode_field(self) -> None:
        assert "pipeline_mode" in self._read()

    def test_has_full_mode(self) -> None:
        assert '"full"' in self._read()

    def test_has_partial_mode(self) -> None:
        assert '"partial"' in self._read()

    def test_has_fallback_mode(self) -> None:
        assert '"fallback"' in self._read()

    def test_has_skills_active_field(self) -> None:
        assert "skills_active" in self._read()

    def test_has_composed_answer_field(self) -> None:
        assert "composed_answer" in self._read()

    def test_uses_asyncio_gather(self) -> None:
        """Skills يجب أن تُستدعى بالتوازي."""
        assert "asyncio.gather" in self._read()

    def test_propagates_correlation_id(self) -> None:
        assert "X-Correlation-ID" in self._read()

    def test_has_run_skills_pipeline_function(self) -> None:
        assert "run_skills_pipeline" in self._read()


# ── 6. Service Dependencies Tests ─────────────────────────────────────────────


class TestServiceDependencies:
    """يتحقق من أن كل خدمة تملك prometheus-client."""

    SERVICES: ClassVar[list[str]] = [
        "orchestrator_service",
        "user_service",
        "planning_agent",
        "conversation_service",
        "research_agent",
        "reasoning_agent",
        "content_retrieval_skill",
    ]

    def test_all_services_have_requirements_txt(self) -> None:
        for svc in self.SERVICES:
            req = list(pathlib.Path(f"microservices/{svc}").glob("requirements.txt"))
            assert req, f"microservices/{svc} missing requirements.txt"

    def test_all_services_have_prometheus_client(self) -> None:
        for svc in self.SERVICES:
            req_files = list(pathlib.Path(f"microservices/{svc}").glob("requirements.txt"))
            assert req_files, f"microservices/{svc} missing requirements.txt"
            content = req_files[0].read_text().lower()
            assert "prometheus" in content, (
                f"microservices/{svc}/requirements.txt missing prometheus-client"
            )

    def test_all_services_have_prom_metrics_py(self) -> None:
        for svc in self.SERVICES:
            metrics_files = list(pathlib.Path(f"microservices/{svc}").rglob("prom_metrics.py"))
            assert metrics_files, f"microservices/{svc} missing prom_metrics.py"

    def test_all_services_have_main_py(self) -> None:
        for svc in self.SERVICES:
            main_files = list(pathlib.Path(f"microservices/{svc}").rglob("main.py"))
            assert main_files, f"microservices/{svc} missing main.py"

    def test_all_services_have_health_endpoint(self) -> None:
        for svc in self.SERVICES:
            main_files = list(pathlib.Path(f"microservices/{svc}").rglob("main.py"))
            assert main_files, f"microservices/{svc} missing main.py"
            content = main_files[0].read_text()
            assert "health" in content.lower(), (
                f"microservices/{svc}/main.py missing /health endpoint"
            )


# ── 7. OrchestratorClient JWT Tests ───────────────────────────────────────────


class TestOrchestratorClientJWT:
    """يتحقق من أن OrchestratorClient يُولِّد JWT داخلي صحيح."""

    CLIENT_SRC = pathlib.Path("app/infrastructure/clients/orchestrator_client.py")

    def _read(self) -> str:
        return self.CLIENT_SRC.read_text()

    def test_has_service_jwt_builder(self) -> None:
        assert "_build_service_jwt" in self._read()

    def test_sends_authorization_header(self) -> None:
        assert "Authorization" in self._read()

    def test_sends_correlation_id(self) -> None:
        assert "X-Correlation-ID" in self._read()

    def test_sends_service_source_header(self) -> None:
        assert "X-Service-Source" in self._read()

    def test_uses_routing_policy(self) -> None:
        assert "ChatRoutingPolicy" in self._read()
        assert "from_environment" in self._read()

    def test_streams_ndjson(self) -> None:
        assert "stream=True" in self._read()
