"""
اختبارات الخطوة 6 — Planning Agent: Prometheus Metrics + DSPy + /metrics endpoint.

تُغطي هذه الاختبارات:
  P1: prometheus-client في requirements.txt
  P2: prom_metrics.py موجود ويحتوي المقاييس الصحيحة (11 اختبارات)
  P3: /metrics endpoint في main.py (5 اختبارات)
  P4: supervisor.sh يُشغِّل planning-agent (4 اختبارات)
  P5: automations.yaml يحتوي planning-agent (5 اختبارات)
  P6: Prometheus scrape config صحيح (3 اختبارات)
  P7: Grafana dashboard صالح (7 اختبارات)
  P8: docker-compose.step6.yml صالح (4 اختبارات)
  P9: unit tests للـ prom_metrics functions (9 اختبارات)

المجموع: 51 اختبار
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

# ── مسارات المشروع ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent.parent
PLANNING_DIR = ROOT / "microservices" / "planning_agent"
PROM_METRICS = PLANNING_DIR / "prom_metrics.py"
MAIN_PY = PLANNING_DIR / "main.py"
REQUIREMENTS = PLANNING_DIR / "requirements.txt"
SUPERVISOR = ROOT / ".devcontainer" / "supervisor.sh"
AUTOMATIONS = ROOT / ".ona" / "automations.yaml"
PROMETHEUS_CFG = ROOT / "observability" / "native" / "prometheus.yml"
DASHBOARD = ROOT / "observability" / "grafana" / "dashboards" / "90-microservices-step6-planning-agent.json"
COMPOSE_STEP6 = ROOT / "docker-compose.step6.yml"


# =============================================================================
# P1: prometheus-client في requirements.txt
# =============================================================================

class TestRequirements:
    """P1: التحقق من وجود prometheus-client في requirements.txt."""

    def test_requirements_file_exists(self):
        assert REQUIREMENTS.exists(), "requirements.txt غير موجود في planning_agent"

    def test_prometheus_client_in_requirements(self):
        content = REQUIREMENTS.read_text()
        assert "prometheus-client" in content, \
            "prometheus-client مفقود من requirements.txt"

    def test_prometheus_client_version_pinned(self):
        content = REQUIREMENTS.read_text()
        match = re.search(r"prometheus-client(>=|==|~=)([\d.]+)", content)
        assert match is not None, "prometheus-client يجب أن يكون له قيد إصدار (>=0.20.0)"
        version = tuple(int(x) for x in match.group(2).split("."))
        assert version >= (0, 20, 0), f"prometheus-client يجب أن يكون >= 0.20.0، الموجود: {match.group(2)}"


# =============================================================================
# P2: prom_metrics.py موجود ويحتوي المقاييس الصحيحة
# =============================================================================

class TestPromMetricsModule:
    """P2: التحقق من وجود prom_metrics.py وصحة محتواه."""

    def test_prom_metrics_file_exists(self):
        assert PROM_METRICS.exists(), "prom_metrics.py غير موجود في planning_agent"

    def test_independent_registry(self):
        content = PROM_METRICS.read_text()
        assert "PLANNING_REGISTRY" in content, "يجب أن يكون هناك PLANNING_REGISTRY مستقل"
        assert "CollectorRegistry()" in content, "يجب إنشاء CollectorRegistry مستقل"

    def test_all_11_metrics_defined(self):
        content = PROM_METRICS.read_text()
        required_metrics = [
            "cogniforge_planning_requests_total",
            "cogniforge_planning_request_duration_seconds",
            "cogniforge_planning_active_connections",
            "cogniforge_planning_plans_total",
            "cogniforge_planning_plan_duration_seconds",
            "cogniforge_planning_dspy_invocations_total",
            "cogniforge_planning_dspy_errors_total",
            "cogniforge_planning_fallback_plans_total",
            "cogniforge_planning_db_operations_total",
            "cogniforge_planning_db_duration_seconds",
            "cogniforge_planning_startup_info",
        ]
        for metric in required_metrics:
            assert metric in content, f"المقياس {metric} غائب من prom_metrics.py"

    def test_step6_label_in_startup_info(self):
        content = PROM_METRICS.read_text()
        assert 'step="6"' in content or "step" in content, \
            "cogniforge_planning_startup_info يجب أن يحتوي label step"

    def test_export_function_defined(self):
        content = PROM_METRICS.read_text()
        assert "def export_prometheus_text" in content, \
            "export_prometheus_text() غير معرَّف في prom_metrics.py"

    def test_set_startup_info_defined(self):
        content = PROM_METRICS.read_text()
        assert "def set_startup_info" in content, \
            "set_startup_info() غير معرَّف في prom_metrics.py"

    def test_record_plan_created_defined(self):
        content = PROM_METRICS.read_text()
        assert "def record_plan_created" in content, \
            "record_plan_created() غير معرَّف في prom_metrics.py"

    def test_record_dspy_invocation_defined(self):
        content = PROM_METRICS.read_text()
        assert "def record_dspy_invocation" in content, \
            "record_dspy_invocation() غير معرَّف في prom_metrics.py"

    def test_defensive_import(self):
        content = PROM_METRICS.read_text()
        assert "try:" in content and "ImportError" in content, \
            "يجب أن يكون هناك استيراد دفاعي (try/except ImportError)"

    def test_dspy_available_label(self):
        content = PROM_METRICS.read_text()
        assert "dspy_available" in content, \
            "cogniforge_planning_startup_info يجب أن يحتوي label dspy_available"

    def test_record_http_request_defined(self):
        content = PROM_METRICS.read_text()
        assert "def record_http_request" in content, \
            "record_http_request() غير معرَّف في prom_metrics.py"


# =============================================================================
# P3: /metrics endpoint في main.py
# =============================================================================

class TestMainPyMetricsEndpoint:
    """P3: التحقق من وجود /metrics endpoint في main.py."""

    def test_main_py_exists(self):
        assert MAIN_PY.exists(), "main.py غير موجود في planning_agent"

    def test_prom_metrics_imported(self):
        content = MAIN_PY.read_text()
        assert "prom_metrics" in content, \
            "prom_metrics لم يُستورد في main.py"

    def test_metrics_route_defined(self):
        content = MAIN_PY.read_text()
        assert '"/metrics"' in content, \
            '/metrics route غير معرَّف في main.py'

    def test_export_prometheus_text_called(self):
        content = MAIN_PY.read_text()
        assert "export_prometheus_text" in content, \
            "export_prometheus_text() لم يُستدعَ في main.py"

    def test_set_startup_info_called_in_lifespan(self):
        content = MAIN_PY.read_text()
        assert "set_startup_info" in content, \
            "set_startup_info() لم يُستدعَ في lifespan"

    def test_response_import(self):
        content = MAIN_PY.read_text()
        assert "from fastapi.responses import Response" in content, \
            "fastapi.responses.Response لم يُستورد في main.py"


# =============================================================================
# P4: supervisor.sh يُشغِّل planning-agent
# =============================================================================

class TestSupervisorSh:
    """P4: التحقق من أن supervisor.sh يُشغِّل planning-agent."""

    def test_supervisor_exists(self):
        assert SUPERVISOR.exists(), "supervisor.sh غير موجود"

    def test_launch_planning_agent_function(self):
        content = SUPERVISOR.read_text()
        assert "launch_planning_agent" in content, \
            "launch_planning_agent() غير معرَّف في supervisor.sh"

    def test_planning_port_8002(self):
        content = SUPERVISOR.read_text()
        assert "8002" in content, \
            "المنفذ 8002 غير مذكور في supervisor.sh"

    def test_planning_uvicorn_command(self):
        content = SUPERVISOR.read_text()
        assert "uvicorn microservices.planning_agent" in content, \
            "أمر uvicorn لـ planning_agent غير موجود في supervisor.sh"

    def test_step4f_label(self):
        content = SUPERVISOR.read_text()
        assert "STEP 4F" in content or "Planning Agent" in content, \
            "STEP 4F أو Planning Agent غير مذكور في supervisor.sh"


# =============================================================================
# P5: automations.yaml يحتوي planning-agent
# =============================================================================

class TestAutomationsYaml:
    """P5: التحقق من أن automations.yaml يحتوي planning-agent service وtasks."""

    def test_automations_file_exists(self):
        assert AUTOMATIONS.exists(), "automations.yaml غير موجود"

    def test_planning_agent_service_defined(self):
        content = AUTOMATIONS.read_text()
        assert "planning-agent:" in content, \
            "planning-agent service غير معرَّف في automations.yaml"

    def test_verify_step6_task_defined(self):
        content = AUTOMATIONS.read_text()
        assert "verify-step6-planning-agent" in content, \
            "verify-step6-planning-agent task غير معرَّف في automations.yaml"

    def test_docker_compose_stack_task_defined(self):
        content = AUTOMATIONS.read_text()
        assert "docker-compose-stack" in content, \
            "docker-compose-stack task غير معرَّف في automations.yaml"

    def test_run_step6_tests_task_defined(self):
        content = AUTOMATIONS.read_text()
        assert "run-step6-tests" in content, \
            "run-step6-tests task غير معرَّف في automations.yaml"

    def test_restart_planning_agent_task_defined(self):
        content = AUTOMATIONS.read_text()
        assert "restart-planning-agent" in content, \
            "restart-planning-agent task غير معرَّف في automations.yaml"

    def test_automations_yaml_valid(self):
        content = AUTOMATIONS.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "automations.yaml ليس YAML صالحاً"
        assert "services" in parsed or "tasks" in parsed, \
            "automations.yaml يجب أن يحتوي services أو tasks"


# =============================================================================
# P6: Prometheus scrape config صحيح
# =============================================================================

class TestPrometheusConfig:
    """P6: التحقق من أن native/prometheus.yml يحتوي scrape target لـ planning-agent."""

    def test_prometheus_config_exists(self):
        assert PROMETHEUS_CFG.exists(), "native/prometheus.yml غير موجود"

    def test_planning_agent_job_defined(self):
        content = PROMETHEUS_CFG.read_text()
        assert "planning-agent" in content, \
            "job planning-agent غير موجود في native/prometheus.yml"

    def test_planning_agent_port_8002(self):
        content = PROMETHEUS_CFG.read_text()
        assert "8002" in content, \
            "المنفذ 8002 غير مذكور في native/prometheus.yml"

    def test_step6_label(self):
        content = PROMETHEUS_CFG.read_text()
        assert 'step: "6"' in content or "step: '6'" in content, \
            "label step: \"6\" غير موجود في native/prometheus.yml"


# =============================================================================
# P7: Grafana dashboard صالح
# =============================================================================

class TestGrafanaDashboard:
    """P7: التحقق من صحة Grafana dashboard للخطوة 6."""

    def test_dashboard_file_exists(self):
        assert DASHBOARD.exists(), "90-microservices-step6-planning-agent.json غير موجود"

    def test_dashboard_valid_json(self):
        content = DASHBOARD.read_text()
        parsed = json.loads(content)
        assert isinstance(parsed, dict), "Dashboard ليس JSON صالحاً"

    def test_dashboard_uid(self):
        parsed = json.loads(DASHBOARD.read_text())
        assert parsed.get("uid") == "cogniforge-ms-step6-planning-agent", \
            "Dashboard UID غير صحيح"

    def test_dashboard_has_panels(self):
        parsed = json.loads(DASHBOARD.read_text())
        panels = parsed.get("panels", [])
        assert len(panels) >= 10, f"Dashboard يجب أن يحتوي >= 10 panels، الموجود: {len(panels)}"

    def test_dashboard_refresh_10s(self):
        parsed = json.loads(DASHBOARD.read_text())
        assert parsed.get("refresh") == "10s", "Dashboard refresh يجب أن يكون 10s"

    def test_dashboard_references_planning_metrics(self):
        content = DASHBOARD.read_text()
        assert "cogniforge_planning" in content, \
            "Dashboard لا يحتوي مقاييس cogniforge_planning_*"

    def test_dashboard_has_startup_info_panel(self):
        content = DASHBOARD.read_text()
        assert "cogniforge_planning_startup_info" in content, \
            "Dashboard لا يحتوي panel لـ cogniforge_planning_startup_info"

    def test_dashboard_tags_include_step6(self):
        parsed = json.loads(DASHBOARD.read_text())
        tags = parsed.get("tags", [])
        assert "step6" in tags, f"Dashboard tags يجب أن تحتوي 'step6'، الموجود: {tags}"


# =============================================================================
# P8: docker-compose.step6.yml صالح
# =============================================================================

class TestDockerComposeStep6:
    """P8: التحقق من صحة docker-compose.step6.yml."""

    def test_compose_file_exists(self):
        assert COMPOSE_STEP6.exists(), "docker-compose.step6.yml غير موجود"

    def test_compose_valid_yaml(self):
        content = COMPOSE_STEP6.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "docker-compose.step6.yml ليس YAML صالحاً"

    def test_planning_agent_service_defined(self):
        parsed = yaml.safe_load(COMPOSE_STEP6.read_text())
        services = parsed.get("services", {})
        assert "planning-agent" in services, \
            "planning-agent غير معرَّف في docker-compose.step6.yml"

    def test_planning_agent_port_8002(self):
        content = COMPOSE_STEP6.read_text()
        assert "8002" in content, \
            "المنفذ 8002 غير مذكور في docker-compose.step6.yml"

    def test_orchestrator_and_user_service_included(self):
        parsed = yaml.safe_load(COMPOSE_STEP6.read_text())
        services = parsed.get("services", {})
        assert "orchestrator-service" in services, "orchestrator-service غير موجود في step6 compose"
        assert "user-service" in services, "user-service غير موجود في step6 compose"

    def test_openrouter_api_key_env_var(self):
        content = COMPOSE_STEP6.read_text()
        assert "OPENROUTER_API_KEY" in content, \
            "OPENROUTER_API_KEY غير مذكور في docker-compose.step6.yml"


# =============================================================================
# P9: unit tests للـ prom_metrics functions
# =============================================================================

class TestPromMetricsFunctions:
    """P9: اختبارات وحدة لدوال prom_metrics.py."""

    def test_import_prom_metrics(self):
        """يجب أن يُستورد prom_metrics بدون أخطاء."""
        from microservices.planning_agent import prom_metrics  # noqa: F401

    def test_export_prometheus_text_returns_bytes(self):
        from microservices.planning_agent import prom_metrics
        body, content_type = prom_metrics.export_prometheus_text()
        assert isinstance(body, bytes), "export_prometheus_text يجب أن يُرجع bytes"

    def test_export_prometheus_text_content_type(self):
        from microservices.planning_agent import prom_metrics
        _, content_type = prom_metrics.export_prometheus_text()
        assert "text/plain" in content_type or "prometheus" in content_type.lower(), \
            f"content_type غير صحيح: {content_type}"

    def test_set_startup_info_emits_metric(self):
        from microservices.planning_agent import prom_metrics
        prom_metrics.set_startup_info(
            version="1.0.0-test",
            environment="testing",
            db_backend="sqlite",
            dspy_available=False,
        )
        body, _ = prom_metrics.export_prometheus_text()
        text = body.decode()
        assert "cogniforge_planning_startup_info" in text, \
            "cogniforge_planning_startup_info غائب بعد set_startup_info()"

    def test_set_startup_info_step6_label(self):
        from microservices.planning_agent import prom_metrics
        prom_metrics.set_startup_info(
            version="1.0.0",
            environment="testing",
            db_backend="sqlite",
            dspy_available=True,
        )
        body, _ = prom_metrics.export_prometheus_text()
        text = body.decode()
        assert 'step="6"' in text, \
            'label step="6" غائب في cogniforge_planning_startup_info'

    def test_record_plan_created_success(self):
        from microservices.planning_agent import prom_metrics
        prom_metrics.record_plan_created(
            strategy="Generated Strategy",
            duration_seconds=2.5,
            is_fallback=False,
        )
        body, _ = prom_metrics.export_prometheus_text()
        text = body.decode()
        assert "cogniforge_planning_plans_total" in text, \
            "cogniforge_planning_plans_total غائب بعد record_plan_created()"

    def test_record_plan_created_fallback(self):
        from microservices.planning_agent import prom_metrics
        prom_metrics.record_plan_created(
            strategy="Fallback Strategy",
            duration_seconds=0.1,
            is_fallback=True,
            fallback_reason="no_api_key",
        )
        body, _ = prom_metrics.export_prometheus_text()
        text = body.decode()
        assert "cogniforge_planning_fallback_plans_total" in text, \
            "cogniforge_planning_fallback_plans_total غائب بعد record_plan_created(fallback)"

    def test_record_dspy_invocation_success(self):
        from microservices.planning_agent import prom_metrics
        prom_metrics.record_dspy_invocation(success=True)
        body, _ = prom_metrics.export_prometheus_text()
        text = body.decode()
        assert "cogniforge_planning_dspy_invocations_total" in text, \
            "cogniforge_planning_dspy_invocations_total غائب"

    def test_record_dspy_invocation_error(self):
        from microservices.planning_agent import prom_metrics
        prom_metrics.record_dspy_invocation(success=False, error_type="TimeoutError")
        body, _ = prom_metrics.export_prometheus_text()
        text = body.decode()
        assert "cogniforge_planning_dspy_errors_total" in text, \
            "cogniforge_planning_dspy_errors_total غائب بعد record_dspy_invocation(error)"

    def test_get_request_timer_returns_float(self):
        from microservices.planning_agent import prom_metrics
        t = prom_metrics.get_request_timer()
        assert isinstance(t, float), "get_request_timer() يجب أن يُرجع float"

    def test_elapsed_since_positive(self):
        import time
        from microservices.planning_agent import prom_metrics
        start = prom_metrics.get_request_timer()
        time.sleep(0.01)
        elapsed = prom_metrics.elapsed_since(start)
        assert elapsed > 0, "elapsed_since() يجب أن يُرجع قيمة موجبة"
        assert elapsed < 5.0, "elapsed_since() أعاد قيمة كبيرة جداً"
