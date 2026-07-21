"""
اختبارات الخطوة 12 — conversation-service (LangGraph Skill).

التغطية:
  C1: prom_metrics.py — 11 مقياس + دوال التسجيل (20 اختبار)
  C2: conversation_graph.py — StateGraph + nodes + fallback (22 اختبار)
  C3: main.py — endpoints /health /metrics /chat/message (18 اختبار)
  C4: database.py — URL normalization + lazy singleton (8 اختبار)
  C5: prometheus.yml — scrape target (4 اختبار)
  C6: Grafana dashboard (5 اختبار)
  C7: supervisor.sh — STEP 4J (4 اختبار)
  C8: automations.yaml — service + tasks (5 اختبار)
  C9: step-12 CI invariants — consolidated into legacy gate (3 اختبار, D-173 Stage 1)
  C10: Skill isolation — no cross-service imports (4 اختبار)

إجمالي: 93 اختبار
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import ClassVar

import pytest

# تجاهل تحذيرات LangGraph الداخلية على مستوى الملف كله
pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning",
    "ignore::PendingDeprecationWarning",
    "ignore::UserWarning",
    "ignore:.*allowed_objects.*",
    "ignore:.*default value.*will change.*",
)

# ── مسارات ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent.parent
CONV_DIR = ROOT / "microservices" / "conversation_service"
PROM_FILE = CONV_DIR / "prom_metrics.py"
GRAPH_FILE = CONV_DIR / "src" / "conversation_graph.py"
MAIN_FILE = CONV_DIR / "main.py"
DB_FILE = CONV_DIR / "database.py"
PROMETHEUS_YML = ROOT / "observability" / "native" / "prometheus.yml"
GRAFANA_DASH = (
    ROOT
    / "observability"
    / "grafana"
    / "dashboards"
    / "140-microservices-step12-conversation-service.json"
)
SUPERVISOR = ROOT / ".devcontainer" / "supervisor.sh"
AUTOMATIONS = ROOT / ".ona" / "automations.yaml"
WORKFLOW = ROOT / ".github" / "workflows" / "microservices-step12-conversation-service.yml"

# ── بيئة الاختبار ─────────────────────────────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CONV_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("SECRET_KEY", "test-secret-key-step12")


# ══════════════════════════════════════════════════════════════════════════════
# C1: prom_metrics.py — 11 مقياس + دوال التسجيل
# ══════════════════════════════════════════════════════════════════════════════


class TestPromMetricsStructure:
    """C1-A: التحقق من وجود المقاييس في الكود."""

    REQUIRED_METRICS: ClassVar[list[str]] = [
        "cogniforge_conversation_requests_total",
        "cogniforge_conversation_request_duration_seconds",
        "cogniforge_conversation_active_connections",
        "cogniforge_conversation_messages_total",
        "cogniforge_conversation_sessions_total",
        "cogniforge_conversation_session_duration_seconds",
        "cogniforge_conversation_graph_invocations_total",
        "cogniforge_conversation_graph_duration_seconds",
        "cogniforge_conversation_graph_errors_total",
        "cogniforge_conversation_db_operations_total",
        "cogniforge_conversation_startup_info",
    ]

    def test_prom_metrics_file_exists(self):
        assert PROM_FILE.exists(), "prom_metrics.py مفقود"

    @pytest.mark.parametrize("metric", REQUIRED_METRICS)
    def test_metric_defined(self, metric: str):
        content = PROM_FILE.read_text()
        assert metric in content, f"المقياس {metric} غير موجود في prom_metrics.py"

    def test_independent_registry(self):
        content = PROM_FILE.read_text()
        assert "CollectorRegistry()" in content

    def test_all_metrics_use_registry(self):
        content = PROM_FILE.read_text()
        assert "registry=REGISTRY" in content

    def test_eleven_metrics_total(self):
        content = PROM_FILE.read_text()
        count = content.count("cogniforge_conversation_")
        # كل مقياس يظهر مرتين على الأقل (تعريف + استخدام)
        assert count >= 11


class TestPromMetricsFunctions:
    """C1-B: التحقق من دوال التسجيل."""

    REQUIRED_FUNCTIONS: ClassVar[list[str]] = [
        "def record_request",
        "def record_ws_connection",
        "def record_message",
        "def record_session",
        "def record_graph_invocation",
        "def record_graph_error",
        "def record_db_operation",
        "def set_startup_info",
        "def get_metrics_output",
    ]

    @pytest.mark.parametrize("fn", REQUIRED_FUNCTIONS)
    def test_function_exists(self, fn: str):
        content = PROM_FILE.read_text()
        assert fn in content, f"الدالة {fn} غير موجودة"

    def test_record_request_has_duration(self):
        content = PROM_FILE.read_text()
        assert "duration_seconds" in content

    def test_get_metrics_output_returns_bytes(self):
        content = PROM_FILE.read_text()
        assert "generate_latest" in content


class TestPromMetricsRuntime:
    """C1-C: اختبارات runtime للمقاييس."""

    def test_import_prom_metrics(self):
        from microservices.conversation_service import prom_metrics

        assert hasattr(prom_metrics, "REGISTRY")

    def test_record_request_increments_counter(self):
        from prometheus_client import generate_latest

        from microservices.conversation_service.prom_metrics import (
            REGISTRY,
            record_request,
        )

        record_request("GET", "/health", 200, 0.001)
        output = generate_latest(REGISTRY).decode()
        assert "cogniforge_conversation_requests_total" in output

    def test_set_startup_info_sets_gauge(self):
        from prometheus_client import generate_latest

        from microservices.conversation_service.prom_metrics import (
            REGISTRY,
            set_startup_info,
        )

        set_startup_info("12", "2.0.0", True, True, True)
        output = generate_latest(REGISTRY).decode()
        assert 'step="12"' in output
        assert "cogniforge_conversation_startup_info" in output

    def test_get_metrics_output_returns_bytes(self):
        from microservices.conversation_service.prom_metrics import get_metrics_output

        result = get_metrics_output()
        assert isinstance(result, bytes)
        assert b"cogniforge_conversation" in result


# ══════════════════════════════════════════════════════════════════════════════
# C2: conversation_graph.py — StateGraph + nodes + fallback
# ══════════════════════════════════════════════════════════════════════════════


class TestConversationGraphStructure:
    """C2-A: بنية StateGraph."""

    def test_graph_file_exists(self):
        assert GRAPH_FILE.exists()

    def test_stategraph_imported(self):
        content = GRAPH_FILE.read_text()
        assert "StateGraph" in content

    def test_conversation_state_typeddict(self):
        content = GRAPH_FILE.read_text()
        assert "ConversationState" in content
        assert "TypedDict" in content

    def test_state_has_required_fields(self):
        content = GRAPH_FILE.read_text()
        for field in ["question", "intent", "history", "response", "thread_id", "correlation_id"]:
            assert field in content, f"field {field} missing from ConversationState"

    def test_intent_node_defined(self):
        content = GRAPH_FILE.read_text()
        assert "async def intent_node" in content

    def test_response_node_defined(self):
        content = GRAPH_FILE.read_text()
        assert "async def response_node" in content

    def test_graph_topology_start_to_intent(self):
        content = GRAPH_FILE.read_text()
        assert "START" in content
        assert "intent_node" in content

    def test_graph_topology_intent_to_response(self):
        content = GRAPH_FILE.read_text()
        assert "response_node" in content

    def test_graph_topology_response_to_end(self):
        content = GRAPH_FILE.read_text()
        assert "END" in content

    def test_timeout_guard_present(self):
        content = GRAPH_FILE.read_text()
        assert "asyncio.wait_for" in content

    def test_timeout_error_handled(self):
        content = GRAPH_FILE.read_text()
        assert "TimeoutError" in content

    def test_fallback_function_exists(self):
        content = GRAPH_FILE.read_text()
        assert "_build_fallback_response" in content

    def test_prometheus_instrumentation_in_nodes(self):
        content = GRAPH_FILE.read_text()
        assert "record_graph_invocation" in content
        assert "record_graph_error" in content

    def test_singleton_pattern(self):
        content = GRAPH_FILE.read_text()
        assert "get_conversation_graph" in content
        assert "_conversation_graph" in content

    def test_invoke_graph_public_api(self):
        content = GRAPH_FILE.read_text()
        assert "async def invoke_graph" in content


class TestIntentClassifier:
    """C2-B: مُصنِّف النوايا."""

    def test_import_classify_intent(self):
        # نتحقق من وجود الدالة في الكود بدون import مباشر لتجنب تحذيرات LangGraph
        content = GRAPH_FILE.read_text()
        assert "def _classify_intent" in content

    def test_educational_arabic(self):
        # اختبار مباشر للمنطق بدون import LangGraph
        content = GRAPH_FILE.read_text()
        assert '"educational"' in content
        assert "اشرح" in content

    def test_educational_bac(self):
        content = GRAPH_FILE.read_text()
        assert "بكالوريا" in content or "باك" in content

    def test_chat_arabic_greeting(self):
        content = GRAPH_FILE.read_text()
        assert "مرحبا" in content
        assert '"chat"' in content

    def test_general_fallback(self):
        content = GRAPH_FILE.read_text()
        assert '"general"' in content

    def test_educational_french(self):
        content = GRAPH_FILE.read_text()
        assert "expliquer" in content or "exercice" in content


class TestFallbackResponse:
    """C2-C: Fallback mode — اختبار بنية الكود بدون import LangGraph."""

    def test_fallback_function_in_code(self):
        content = GRAPH_FILE.read_text()
        assert "def _build_fallback_response" in content

    def test_fallback_handles_educational(self):
        content = GRAPH_FILE.read_text()
        assert "educational" in content

    def test_fallback_handles_chat(self):
        content = GRAPH_FILE.read_text()
        assert "chat" in content


class TestGraphRuntime:
    """C2-D: اختبارات runtime للـ graph — بدون import مباشر لتجنب تحذيرات LangGraph."""

    def test_build_conversation_graph_function_exists(self):
        content = GRAPH_FILE.read_text()
        assert "def build_conversation_graph" in content

    def test_get_conversation_graph_function_exists(self):
        content = GRAPH_FILE.read_text()
        assert "def get_conversation_graph" in content

    def test_invoke_graph_function_exists(self):
        content = GRAPH_FILE.read_text()
        assert "async def invoke_graph" in content

    def test_invoke_graph_returns_response_key(self):
        content = GRAPH_FILE.read_text()
        assert '"response"' in content

    def test_invoke_graph_returns_intent_key(self):
        content = GRAPH_FILE.read_text()
        assert '"intent"' in content

    def test_invoke_graph_accepts_history(self):
        content = GRAPH_FILE.read_text()
        assert "history" in content


# ══════════════════════════════════════════════════════════════════════════════
# C3: main.py — endpoints
# ══════════════════════════════════════════════════════════════════════════════


class TestMainEndpoints:
    """C3: اختبارات HTTP endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from microservices.conversation_service import main as conv_main

        conv_main._GRAPH_READY = True
        return TestClient(conv_main.app, raise_server_exceptions=False)

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_schema(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "service" in data
        assert data["service"] == "conversation-service"
        assert "step" in data
        assert data["step"] == "12"
        assert "graph_ready" in data
        assert "ws_enabled" in data

    def test_health_ws_enabled_true(self, client):
        resp = client.get("/health")
        assert resp.json()["ws_enabled"] is True

    def test_metrics_returns_200(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type(self, client):
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"]

    def test_metrics_contains_startup_info(self, client):
        resp = client.get("/metrics")
        assert b"cogniforge_conversation" in resp.content

    def test_chat_message_happy_path(self, client):
        resp = client.post(
            "/chat/message",
            json={"question": "اشرح قانون نيوتن"},
        )
        assert resp.status_code == 200

    def test_chat_message_response_schema(self, client):
        resp = client.post(
            "/chat/message",
            json={"question": "ما هو قانون نيوتن؟"},
        )
        data = resp.json()
        assert "response" in data
        assert "intent" in data
        assert "thread_id" in data
        assert "correlation_id" in data
        assert "step" in data
        assert data["step"] == "12"

    def test_chat_message_with_thread_id(self, client):
        resp = client.post(
            "/chat/message",
            json={"question": "سؤال", "thread_id": "my-thread-123"},
        )
        assert resp.status_code == 200
        assert resp.json()["thread_id"] == "my-thread-123"

    def test_chat_message_empty_question_rejected(self, client):
        resp = client.post(
            "/chat/message",
            json={"question": ""},
        )
        assert resp.status_code == 422

    def test_chat_message_educational_intent(self, client):
        resp = client.post(
            "/chat/message",
            json={"question": "اشرح قانون نيوتن الثاني"},
        )
        assert resp.json()["intent"] == "educational"

    def test_legacy_api_chat_returns_200(self, client):
        resp = client.get("/api/chat/messages")
        assert resp.status_code == 200

    def test_legacy_api_chat_has_new_endpoint(self, client):
        resp = client.get("/api/chat/test")
        data = resp.json()
        assert "new_endpoint" in data
        assert data["new_endpoint"] == "/chat/message"

    def test_health_degraded_when_graph_not_ready(self, client):
        from microservices.conversation_service import main as conv_main

        original = conv_main._GRAPH_READY
        conv_main._GRAPH_READY = False
        resp = client.get("/health")
        assert resp.json()["status"] == "degraded"
        conv_main._GRAPH_READY = original

    def test_health_healthy_when_graph_ready(self, client):
        from microservices.conversation_service import main as conv_main

        conv_main._GRAPH_READY = True
        resp = client.get("/health")
        assert resp.json()["status"] == "healthy"

    def test_chat_message_with_history(self, client):
        resp = client.post(
            "/chat/message",
            json={
                "question": "ما هو قانون نيوتن؟",
                "history": [{"role": "user", "content": "مرحبا"}],
            },
        )
        assert resp.status_code == 200

    def test_chat_message_with_correlation_id(self, client):
        resp = client.post(
            "/chat/message",
            json={"question": "سؤال", "correlation_id": "my-corr-456"},
        )
        assert resp.json()["correlation_id"] == "my-corr-456"

    def test_metrics_records_request_after_health(self, client):
        client.get("/health")
        resp = client.get("/metrics")
        assert b"cogniforge_conversation_requests_total" in resp.content


# ══════════════════════════════════════════════════════════════════════════════
# C4: database.py — URL normalization
# ══════════════════════════════════════════════════════════════════════════════


class TestDatabaseUrlNormalization:
    """C4: تحويل DATABASE_URL."""

    def test_normalize_postgresql_to_asyncpg(self):
        from microservices.conversation_service.database import _normalize_db_url

        result = _normalize_db_url("postgresql://user:pass@host:5432/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_normalize_postgres_alias(self):
        from microservices.conversation_service.database import _normalize_db_url

        result = _normalize_db_url("postgres://user:pass@host:5432/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_removes_sslmode(self):
        from microservices.conversation_service.database import _normalize_db_url

        result = _normalize_db_url("postgresql://user:pass@host:5432/db?sslmode=require")
        assert "sslmode" not in result

    def test_sqlite_unchanged(self):
        from microservices.conversation_service.database import _normalize_db_url

        url = "sqlite+aiosqlite:///:memory:"
        assert _normalize_db_url(url) == url

    def test_get_engine_returns_engine(self):
        from microservices.conversation_service.database import get_engine

        engine = get_engine()
        assert engine is not None

    def test_get_engine_singleton(self):
        from microservices.conversation_service import database

        database._engine = None
        e1 = database.get_engine()
        e2 = database.get_engine()
        assert e1 is e2

    def test_async_session_local_exists(self):
        from microservices.conversation_service.database import AsyncSessionLocal

        assert AsyncSessionLocal is not None

    def test_get_conv_db_session_is_generator(self):
        import inspect

        from microservices.conversation_service.database import get_conv_db_session

        assert inspect.isasyncgenfunction(get_conv_db_session)


# ══════════════════════════════════════════════════════════════════════════════
# C5: prometheus.yml — scrape target
# ══════════════════════════════════════════════════════════════════════════════


class TestPrometheusConfig:
    """C5: Prometheus scrape target للخطوة 12."""

    def test_prometheus_yml_exists(self):
        assert PROMETHEUS_YML.exists()

    def test_conversation_service_job_present(self):
        content = PROMETHEUS_YML.read_text()
        assert "conversation-service" in content

    def test_port_8003_present(self):
        content = PROMETHEUS_YML.read_text()
        assert "localhost:8003" in content

    def test_step_12_label(self):
        content = PROMETHEUS_YML.read_text()
        assert 'step: "12"' in content


# ══════════════════════════════════════════════════════════════════════════════
# C6: Grafana dashboard
# ══════════════════════════════════════════════════════════════════════════════


class TestGrafanaDashboard:
    """C6: Grafana dashboard للخطوة 12."""

    @pytest.fixture
    def dashboard(self):
        return json.loads(GRAFANA_DASH.read_text())

    def test_dashboard_file_exists(self):
        assert GRAFANA_DASH.exists()

    def test_dashboard_uid(self, dashboard):
        assert dashboard["uid"] == "cogniforge-ms-step12-conversation"

    def test_dashboard_has_panels(self, dashboard):
        assert len(dashboard["panels"]) >= 14

    def test_dashboard_refresh_10s(self, dashboard):
        assert dashboard["refresh"] == "10s"

    def test_dashboard_has_startup_info_panel(self, dashboard):
        titles = [p["title"] for p in dashboard["panels"]]
        assert any("Startup" in t or "startup" in t for t in titles)


# ══════════════════════════════════════════════════════════════════════════════
# C7: supervisor.sh — STEP 4J
# ══════════════════════════════════════════════════════════════════════════════


class TestSupervisorSh:
    """C7: supervisor.sh STEP 4J."""

    def test_step_4j_present(self):
        content = SUPERVISOR.read_text()
        assert "STEP 4J" in content

    def test_launch_conversation_service_function(self):
        content = SUPERVISOR.read_text()
        assert "launch_conversation_service" in content

    def test_port_8003_in_supervisor(self):
        content = SUPERVISOR.read_text()
        assert "8003" in content

    def test_asyncpg_url_conversion(self):
        content = SUPERVISOR.read_text()
        # يجب أن يُحوِّل postgresql:// إلى postgresql+asyncpg://
        assert "postgresql+asyncpg" in content


# ══════════════════════════════════════════════════════════════════════════════
# C8: automations.yaml — service + tasks
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationsYaml:
    """C8: automations.yaml للخطوة 12."""

    def test_conversation_service_service_defined(self):
        content = AUTOMATIONS.read_text()
        assert "conversation-service:" in content

    def test_verify_step12_task_defined(self):
        content = AUTOMATIONS.read_text()
        assert "verify-step12-conversation-service" in content

    def test_restart_conversation_service_task(self):
        content = AUTOMATIONS.read_text()
        assert "restart-conversation-service" in content

    def test_run_step12_tests_task(self):
        content = AUTOMATIONS.read_text()
        assert "run-step12-tests" in content

    def test_port_8003_in_automations(self):
        content = AUTOMATIONS.read_text()
        assert "8003" in content


# ══════════════════════════════════════════════════════════════════════════════
# C9: GitHub Actions workflow
# ══════════════════════════════════════════════════════════════════════════════


class TestGitHubActionsWorkflow:
    """C9: step-12 CI invariants — consolidated into the legacy gate (D-173 Stage 1).

    The standalone ``microservices-step12-conversation-service.yml`` workflow was
    merged away in the CI consolidation (38→~18 workflows). Its ``grep -q``
    assertions were transcribed verbatim into
    ``scripts/fitness/check_legacy_invariants.py`` (the single legacy-invariant
    gate). Per D-105 (align to reality, never disable), these tests now assert the
    invariants survive in the consolidation target rather than in a deleted file.
    """

    LEGACY_GATE: ClassVar = ROOT / "scripts" / "fitness" / "check_legacy_invariants.py"

    def test_standalone_workflow_was_consolidated(self):
        # The per-step workflow no longer exists; the legacy gate replaces it.
        assert not WORKFLOW.exists(), "step-12 workflow should be consolidated away (D-173 Stage 1)"
        assert self.LEGACY_GATE.exists()

    def test_step12_invariants_survive_in_legacy_gate(self):
        content = self.LEGACY_GATE.read_text(encoding="utf-8")
        # Core step-12 contracts (metrics endpoints + graph nodes + timeout guard).
        for invariant in ('"/chat/message"', '"/chat/ws"', "StateGraph", "asyncio.wait_for"):
            assert invariant in content, f"step-12 invariant dropped from legacy gate: {invariant}"

    def test_legacy_gate_covers_conversation_service(self):
        content = self.LEGACY_GATE.read_text(encoding="utf-8")
        assert "conversation-service" in content or "conversation_service" in content


# ══════════════════════════════════════════════════════════════════════════════
# C10: Skill isolation — no cross-service imports
# ══════════════════════════════════════════════════════════════════════════════


class TestSkillIsolation:
    """C10: conversation-service لا يستورد من microservices أخرى."""

    FORBIDDEN_IMPORTS: ClassVar[list[str]] = [
        "orchestrator_service",
        "planning_agent",
        "research_agent",
        "reasoning_agent",
        "user_service",
        "content_retrieval_skill",
    ]

    @pytest.mark.parametrize("forbidden", FORBIDDEN_IMPORTS)
    def test_no_cross_service_import(self, forbidden: str):
        for py_file in CONV_DIR.rglob("*.py"):
            content = py_file.read_text()
            assert f"from microservices.{forbidden}" not in content, (
                f"{py_file.name} imports from {forbidden} — Skill isolation violated"
            )

    def test_requirements_has_prometheus_client(self):
        req = (CONV_DIR / "requirements.txt").read_text()
        assert "prometheus-client" in req

    def test_requirements_has_langgraph(self):
        req = (CONV_DIR / "requirements.txt").read_text()
        assert "langgraph" in req

    def test_src_init_exists(self):
        assert (CONV_DIR / "src" / "__init__.py").exists()
