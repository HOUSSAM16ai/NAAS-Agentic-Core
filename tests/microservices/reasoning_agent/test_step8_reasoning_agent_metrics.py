"""
اختبارات Step 8 — reasoning-agent Prometheus metrics.

المجموعات:
  R1: requirements.txt — prometheus-client موجود
  R2: prom_metrics.py — 11 مقياساً + دوال عامة
  R3: main.py — /metrics endpoint + /health محسَّن + step=8
  R4: supervisor.sh — launch_reasoning_agent() على :8008
  R5: automations.yaml — reasoning-agent service + tasks
  R6: prometheus.yml — scrape target :8008 + step=8
  R7: Grafana dashboard — JSON valid + UID + panels
  R8: unit tests — prom_metrics functions بدون I/O
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

# ── مسارات المشروع ────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent.parent
REASONING_DIR = ROOT / "microservices" / "reasoning_agent"
REQUIREMENTS = REASONING_DIR / "requirements.txt"
PROM_METRICS = REASONING_DIR / "prom_metrics.py"
MAIN_PY = REASONING_DIR / "main.py"
ROUTES_PY = REASONING_DIR / "src" / "api" / "routes.py"
SUPERVISOR = ROOT / ".devcontainer" / "supervisor.sh"
AUTOMATIONS = ROOT / ".ona" / "automations.yaml"
PROMETHEUS_CFG = ROOT / "observability" / "native" / "prometheus.yml"
DASHBOARD = (
    ROOT
    / "observability"
    / "grafana"
    / "dashboards"
    / "110-microservices-step8-reasoning-agent.json"
)


# ===========================================================================
# R1: requirements.txt
# ===========================================================================


class TestRequirements:
    """يتحقق من وجود prometheus-client في requirements.txt."""

    def test_requirements_file_exists(self):
        assert REQUIREMENTS.exists(), "requirements.txt غير موجود"

    def test_prometheus_client_present(self):
        content = REQUIREMENTS.read_text()
        assert "prometheus-client" in content, "prometheus-client مفقود من requirements.txt"

    def test_prometheus_client_version(self):
        content = REQUIREMENTS.read_text()
        match = re.search(r"prometheus-client(>=|==)([\d.]+)", content)
        assert match, "prometheus-client يجب أن يحدد إصداراً (>= أو ==)"
        version = match.group(2)
        major, minor = int(version.split(".")[0]), int(version.split(".")[1])
        assert (major, minor) >= (0, 20), (
            f"prometheus-client يجب أن يكون >= 0.20.0، الموجود: {version}"
        )


# ===========================================================================
# R2: prom_metrics.py
# ===========================================================================


class TestPromMetricsFile:
    """يتحقق من وجود prom_metrics.py وصحة محتواه."""

    def test_file_exists(self):
        assert PROM_METRICS.exists(), "prom_metrics.py غير موجود"

    def test_independent_registry(self):
        content = PROM_METRICS.read_text()
        assert "CollectorRegistry" in content, "يجب استخدام CollectorRegistry مستقل"
        assert "_REGISTRY" in content, "_REGISTRY غير معرَّف"

    @pytest.mark.parametrize(
        "metric_name",
        [
            "cogniforge_reasoning_requests_total",
            "cogniforge_reasoning_request_duration_seconds",
            "cogniforge_reasoning_active_connections",
            "cogniforge_reasoning_invocations_total",
            "cogniforge_reasoning_invocation_duration_seconds",
            "cogniforge_reasoning_mcts_expansions_total",
            "cogniforge_reasoning_mcts_errors_total",
            "cogniforge_reasoning_llm_calls_total",
            "cogniforge_reasoning_llm_errors_total",
            "cogniforge_reasoning_fallback_responses_total",
            "cogniforge_reasoning_startup_info",
        ],
    )
    def test_metric_defined(self, metric_name: str):
        content = PROM_METRICS.read_text()
        assert metric_name in content, f"المقياس {metric_name} غير موجود في prom_metrics.py"

    @pytest.mark.parametrize(
        "func_name",
        [
            "export_prometheus_text",
            "set_startup_info",
            "record_http_request",
            "record_reasoning_invocation",
            "record_mcts_expansion",
            "record_mcts_error",
            "record_llm_call",
            "record_llm_error",
            "record_fallback_response",
            "set_active_connections",
            "elapsed_since",
        ],
    )
    def test_public_function_defined(self, func_name: str):
        content = PROM_METRICS.read_text()
        assert f"def {func_name}" in content, f"الدالة {func_name} غير موجودة في prom_metrics.py"

    def test_defensive_import(self):
        content = PROM_METRICS.read_text()
        assert "try:" in content and "ImportError" in content, (
            "يجب وجود استيراد دفاعي (try/except ImportError) لـ prometheus_client"
        )

    def test_step8_label(self):
        content = PROM_METRICS.read_text()
        assert 'step="8"' in content or "step.*8" in content, (
            "يجب وجود label step=8 في set_startup_info"
        )


# ===========================================================================
# R3: main.py
# ===========================================================================


class TestMainPy:
    """يتحقق من /metrics endpoint و /health المحسَّن في main.py."""

    def test_file_exists(self):
        assert MAIN_PY.exists(), "main.py غير موجود"

    def test_metrics_endpoint_defined(self):
        content = MAIN_PY.read_text()
        assert '"/metrics"' in content, "/metrics endpoint غير معرَّف في main.py"

    def test_export_prometheus_text_called(self):
        content = MAIN_PY.read_text()
        assert "export_prometheus_text" in content, "export_prometheus_text غير مستدعى في main.py"

    def test_prom_metrics_imported(self):
        content = MAIN_PY.read_text()
        assert "prom_metrics" in content, "prom_metrics غير مستورد في main.py"

    def test_health_endpoint_returns_step8(self):
        content = MAIN_PY.read_text()
        assert '"step"' in content or "'step'" in content, (
            "health endpoint يجب أن يُعيد step في main.py"
        )
        assert '"8"' in content or "'8'" in content, "health endpoint يجب أن يُعيد step=8"

    def test_no_import_time_ai_service(self):
        content = MAIN_PY.read_text()
        # main.py يجب ألا يستورد ai_service مباشرةً عند الإقلاع
        assert (
            "from microservices.reasoning_agent.src.services.ai_service import ai_service"
            not in content
        ), "ISS-039-B: main.py يستورد ai_service عند الإقلاع"

    def test_lifespan_calls_set_startup_info(self):
        content = MAIN_PY.read_text()
        assert "set_startup_info" in content, "lifespan يجب أن يستدعي set_startup_info"

    def test_response_class_used(self):
        content = MAIN_PY.read_text()
        assert "Response" in content, "يجب استخدام fastapi.responses.Response لـ /metrics"


# ===========================================================================
# R4: supervisor.sh
# ===========================================================================


class TestSupervisorSh:
    """يتحقق من launch_reasoning_agent() في supervisor.sh."""

    def test_file_exists(self):
        assert SUPERVISOR.exists(), "supervisor.sh غير موجود"

    def test_launch_function_defined(self):
        content = SUPERVISOR.read_text()
        assert "launch_reasoning_agent" in content, (
            "launch_reasoning_agent() غير موجودة في supervisor.sh"
        )

    def test_port_8008(self):
        content = SUPERVISOR.read_text()
        assert "8008" in content, "port 8008 غير موجود في supervisor.sh"

    def test_step_4h_marker(self):
        content = SUPERVISOR.read_text()
        assert "4H" in content or "STEP 4H" in content, "STEP 4H marker غير موجود في supervisor.sh"

    def test_idempotent_check(self):
        content = SUPERVISOR.read_text()
        assert "reasoning_agent.main" in content, (
            "idempotent check لـ reasoning_agent.main غير موجود في supervisor.sh"
        )

    def test_openrouter_key_injected(self):
        content = SUPERVISOR.read_text()
        # يجب أن يُحقن OPENROUTER_API_KEY في بيئة الـ process
        assert "OPENROUTER_API_KEY" in content, (
            "OPENROUTER_API_KEY غير محقون في launch_reasoning_agent"
        )


# ===========================================================================
# R5: automations.yaml
# ===========================================================================


class TestAutomationsYaml:
    """يتحقق من reasoning-agent service و tasks في automations.yaml."""

    def test_file_exists(self):
        assert AUTOMATIONS.exists(), "automations.yaml غير موجود"

    def test_reasoning_agent_service(self):
        content = AUTOMATIONS.read_text()
        assert "reasoning-agent:" in content, (
            "reasoning-agent service غير موجود في automations.yaml"
        )

    def test_port_8008_in_service(self):
        content = AUTOMATIONS.read_text()
        assert "8008" in content, "port 8008 غير موجود في automations.yaml"

    def test_verify_step8_task(self):
        content = AUTOMATIONS.read_text()
        assert "verify-step8-reasoning-agent" in content, (
            "verify-step8-reasoning-agent task غير موجود"
        )

    def test_restart_task(self):
        content = AUTOMATIONS.read_text()
        assert "restart-reasoning-agent" in content, "restart-reasoning-agent task غير موجود"

    def test_run_tests_task(self):
        content = AUTOMATIONS.read_text()
        assert "run-step8-tests" in content, "run-step8-tests task غير موجود"

    def test_ready_command_checks_metrics(self):
        content = AUTOMATIONS.read_text()
        assert "cogniforge_reasoning_startup_info" in content, (
            "ready command يجب أن يتحقق من cogniforge_reasoning_startup_info"
        )

    def test_step8_in_header_comment(self):
        content = AUTOMATIONS.read_text()
        assert "Step 8" in content or "step8" in content, (
            "Step 8 غير مذكور في header automations.yaml"
        )


# ===========================================================================
# R6: prometheus.yml
# ===========================================================================


class TestPrometheusConfig:
    """يتحقق من scrape target للـ reasoning-agent في prometheus.yml."""

    def test_file_exists(self):
        assert PROMETHEUS_CFG.exists(), "prometheus.yml غير موجود"

    def test_reasoning_agent_job(self):
        content = PROMETHEUS_CFG.read_text()
        assert "reasoning-agent" in content, "reasoning-agent job غير موجود في prometheus.yml"

    def test_port_8008_target(self):
        content = PROMETHEUS_CFG.read_text()
        assert "8008" in content, "port 8008 غير موجود في prometheus.yml"

    def test_step8_label(self):
        content = PROMETHEUS_CFG.read_text()
        assert 'step: "8"' in content or "step.*8" in content, (
            "step=8 label غير موجود في prometheus.yml"
        )

    def test_metrics_path(self):
        content = PROMETHEUS_CFG.read_text()
        assert "metrics_path: /metrics" in content, (
            "metrics_path: /metrics غير موجود في prometheus.yml"
        )


# ===========================================================================
# R7: Grafana dashboard
# ===========================================================================


class TestGrafanaDashboard:
    """يتحقق من صحة Grafana dashboard للخطوة 8."""

    def test_file_exists(self):
        assert DASHBOARD.exists(), (
            "Dashboard 110-microservices-step8-reasoning-agent.json غير موجود"
        )

    def test_valid_json(self):
        content = DASHBOARD.read_text()
        data = json.loads(content)
        assert isinstance(data, dict), "Dashboard ليس JSON object صالح"

    def test_correct_uid(self):
        data = json.loads(DASHBOARD.read_text())
        assert data.get("uid") == "cogniforge-ms-step8-reasoning-agent", (
            f"UID خاطئ: {data.get('uid')}"
        )

    def test_step8_tag(self):
        data = json.loads(DASHBOARD.read_text())
        assert "step8" in data.get("tags", []), "tag step8 غير موجود في dashboard"

    def test_refresh_10s(self):
        data = json.loads(DASHBOARD.read_text())
        assert data.get("refresh") == "10s", "refresh يجب أن يكون 10s"

    def test_minimum_panels(self):
        data = json.loads(DASHBOARD.read_text())
        panels = data.get("panels", [])
        assert len(panels) >= 15, f"يجب وجود >= 15 panel، الموجود: {len(panels)}"

    def test_references_startup_info_metric(self):
        content = DASHBOARD.read_text()
        assert "cogniforge_reasoning_startup_info" in content, (
            "cogniforge_reasoning_startup_info غير مذكور في dashboard"
        )

    def test_references_invocations_metric(self):
        content = DASHBOARD.read_text()
        assert "cogniforge_reasoning_invocations_total" in content, (
            "cogniforge_reasoning_invocations_total غير مذكور في dashboard"
        )

    def test_references_mcts_metric(self):
        content = DASHBOARD.read_text()
        assert "cogniforge_reasoning_mcts_expansions_total" in content, (
            "cogniforge_reasoning_mcts_expansions_total غير مذكور في dashboard"
        )

    def test_health_matrix_panel(self):
        content = DASHBOARD.read_text()
        assert "Health Matrix" in content or "health matrix" in content.lower(), (
            "Health Matrix panel غير موجود في dashboard"
        )


# ===========================================================================
# R8: unit tests — prom_metrics functions
# ===========================================================================

import sys

# أضف مسار المشروع لـ sys.path حتى يعمل الاستيراد المباشر
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import microservices.reasoning_agent.prom_metrics as _PM  # noqa: N812


class TestPromMetricsFunctions:
    """اختبارات وحدة لدوال prom_metrics بدون I/O."""

    @pytest.fixture(autouse=True)
    def import_prom_metrics(self):
        """يُعيِّن self.pm إلى الـ module المُستورَد مباشرةً."""
        self.pm = _PM

    def test_export_prometheus_text_returns_bytes(self):
        content, ctype = self.pm.export_prometheus_text()
        assert isinstance(content, bytes), "export_prometheus_text يجب أن يُعيد bytes"
        assert "text/plain" in ctype or "text" in ctype, "content_type يجب أن يحتوي text/plain"

    def test_set_startup_info_sets_gauge(self):
        self.pm.set_startup_info(
            version="2.0.0",
            environment="test",
            llm_backend="openrouter",
            mcts_enabled="true",
        )
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_startup_info" in text, (
            "cogniforge_reasoning_startup_info غير موجود في output بعد set_startup_info"
        )

    def test_set_startup_info_step8_label(self):
        self.pm.set_startup_info(version="1.0.0", environment="test")
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert 'step="8"' in text, 'label step="8" غير موجود في metrics output'

    def test_record_http_request_increments_counter(self):
        self.pm.record_http_request(
            method="POST",
            endpoint="/execute",
            status_code=200,
            duration_seconds=0.5,
        )
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_requests_total" in text

    def test_record_reasoning_invocation(self):
        self.pm.record_reasoning_invocation(
            action="reason",
            status="success",
            duration_seconds=2.5,
        )
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_invocations_total" in text

    def test_record_mcts_expansion(self):
        self.pm.record_mcts_expansion(depth=1)
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_mcts_expansions_total" in text

    def test_record_mcts_error(self):
        self.pm.record_mcts_error(error_type="timeout")
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_mcts_errors_total" in text

    def test_record_llm_call(self):
        self.pm.record_llm_call(model="gpt-4o", status="success")
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_llm_calls_total" in text

    def test_record_llm_error(self):
        self.pm.record_llm_error(error_type="rate_limit")
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_llm_errors_total" in text

    def test_record_fallback_response(self):
        self.pm.record_fallback_response(reason="no_api_key")
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_fallback_responses_total" in text

    def test_set_active_connections(self):
        self.pm.set_active_connections(3)
        content, _ = self.pm.export_prometheus_text()
        text = content.decode()
        assert "cogniforge_reasoning_active_connections" in text

    def test_elapsed_since_positive(self):
        start = time.monotonic()
        time.sleep(0.01)
        elapsed = self.pm.elapsed_since(start)
        assert elapsed > 0, "elapsed_since يجب أن يُعيد قيمة موجبة"
        assert elapsed < 5.0, "elapsed_since أعاد قيمة كبيرة جداً"

    def test_get_request_timer_returns_context_manager(self):
        timer = self.pm.get_request_timer(method="GET", endpoint="/health")
        assert hasattr(timer, "__enter__") and hasattr(timer, "__exit__"), (
            "get_request_timer يجب أن يُعيد context manager"
        )
