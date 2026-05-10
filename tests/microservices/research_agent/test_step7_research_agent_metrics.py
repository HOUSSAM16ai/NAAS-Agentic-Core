"""
اختبارات Step 7 — research-agent Prometheus metrics + Tavily + /metrics endpoint.

تغطي:
  R1: prometheus-client + tavily-python في requirements.txt
  R2: prom_metrics.py موجود ويحتوي المقاييس الصحيحة (11 مقياساً)
  R3: /metrics endpoint في main.py
  R4: supervisor.sh يُشغِّل research-agent على :8007
  R5: automations.yaml يحتوي research-agent service + tasks
  R6: Prometheus scrape config صحيح
  R7: Grafana dashboard صالح
  R8: unit tests للـ prom_metrics functions
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

# ── مسارات المشروع ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent.parent
RESEARCH_DIR = ROOT / "microservices" / "research_agent"
PROM_METRICS = RESEARCH_DIR / "prom_metrics.py"
MAIN_PY = RESEARCH_DIR / "main.py"
REQUIREMENTS = RESEARCH_DIR / "requirements.txt"
SUPERVISOR = ROOT / ".devcontainer" / "supervisor.sh"
AUTOMATIONS = ROOT / ".ona" / "automations.yaml"
PROMETHEUS_YML = ROOT / "observability" / "native" / "prometheus.yml"
DASHBOARD = ROOT / "observability" / "grafana" / "dashboards" / "100-microservices-step7-research-agent.json"


# ═══════════════════════════════════════════════════════════════════════════════
# R1: requirements.txt
# ═══════════════════════════════════════════════════════════════════════════════

class TestR1Requirements:
    """التحقق من وجود التبعيات المطلوبة في requirements.txt."""

    def test_prometheus_client_present(self) -> None:
        content = REQUIREMENTS.read_text()
        assert "prometheus-client" in content, "prometheus-client مفقود من requirements.txt"

    def test_tavily_python_present(self) -> None:
        content = REQUIREMENTS.read_text()
        assert "tavily-python" in content, "tavily-python مفقود من requirements.txt"

    def test_fastapi_present(self) -> None:
        content = REQUIREMENTS.read_text()
        assert "fastapi" in content.lower(), "fastapi مفقود من requirements.txt"


# ═══════════════════════════════════════════════════════════════════════════════
# R2: prom_metrics.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestR2PromMetrics:
    """التحقق من وجود prom_metrics.py وصحة محتواه."""

    def test_file_exists(self) -> None:
        assert PROM_METRICS.exists(), "prom_metrics.py غير موجود"

    def test_has_independent_registry(self) -> None:
        content = PROM_METRICS.read_text()
        assert "CollectorRegistry" in content, "CollectorRegistry مفقود"

    def test_metric_requests_total(self) -> None:
        assert "cogniforge_research_requests_total" in PROM_METRICS.read_text()

    def test_metric_request_duration(self) -> None:
        assert "cogniforge_research_request_duration_seconds" in PROM_METRICS.read_text()

    def test_metric_active_connections(self) -> None:
        assert "cogniforge_research_active_connections" in PROM_METRICS.read_text()

    def test_metric_searches_total(self) -> None:
        assert "cogniforge_research_searches_total" in PROM_METRICS.read_text()

    def test_metric_search_duration(self) -> None:
        assert "cogniforge_research_search_duration_seconds" in PROM_METRICS.read_text()

    def test_metric_tavily_calls(self) -> None:
        assert "cogniforge_research_tavily_calls_total" in PROM_METRICS.read_text()

    def test_metric_tavily_errors(self) -> None:
        assert "cogniforge_research_tavily_errors_total" in PROM_METRICS.read_text()

    def test_metric_deep_research(self) -> None:
        assert "cogniforge_research_deep_research_total" in PROM_METRICS.read_text()

    def test_metric_db_operations(self) -> None:
        assert "cogniforge_research_db_operations_total" in PROM_METRICS.read_text()

    def test_metric_db_duration(self) -> None:
        assert "cogniforge_research_db_duration_seconds" in PROM_METRICS.read_text()

    def test_metric_startup_info(self) -> None:
        assert "cogniforge_research_startup" in PROM_METRICS.read_text()

    def test_has_export_function(self) -> None:
        assert "export_prometheus_text" in PROM_METRICS.read_text()

    def test_has_set_startup_info(self) -> None:
        assert "set_startup_info" in PROM_METRICS.read_text()

    def test_has_record_search(self) -> None:
        assert "record_search" in PROM_METRICS.read_text()

    def test_has_record_tavily_call(self) -> None:
        assert "record_tavily_call" in PROM_METRICS.read_text()

    def test_has_record_tavily_error(self) -> None:
        assert "record_tavily_error" in PROM_METRICS.read_text()

    def test_has_record_deep_research(self) -> None:
        assert "record_deep_research" in PROM_METRICS.read_text()

    def test_has_defensive_import(self) -> None:
        content = PROM_METRICS.read_text()
        assert "ImportError" in content, "استيراد دفاعي مفقود"

    def test_step_label_is_7(self) -> None:
        content = PROM_METRICS.read_text()
        assert '"7"' in content or "'7'" in content, 'label step="7" مفقود'


# ═══════════════════════════════════════════════════════════════════════════════
# R3: main.py /metrics endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestR3MainMetricsEndpoint:
    """التحقق من وجود /metrics endpoint في main.py."""

    def test_metrics_route_defined(self) -> None:
        content = MAIN_PY.read_text()
        assert '"/metrics"' in content, '/metrics route مفقود من main.py'

    def test_export_prometheus_text_called(self) -> None:
        content = MAIN_PY.read_text()
        assert "export_prometheus_text" in content, "export_prometheus_text غير مستدعى"

    def test_prom_metrics_imported(self) -> None:
        content = MAIN_PY.read_text()
        assert "prom_metrics" in content, "prom_metrics غير مستورد في main.py"

    def test_set_startup_info_in_lifespan(self) -> None:
        content = MAIN_PY.read_text()
        assert "set_startup_info" in content, "set_startup_info غير مستدعى في lifespan"

    def test_tavily_detection(self) -> None:
        content = MAIN_PY.read_text()
        assert "TAVILY_API_KEY" in content, "TAVILY_API_KEY غير مُكتشَف في main.py"

    def test_response_import(self) -> None:
        content = MAIN_PY.read_text()
        assert "Response" in content, "fastapi.responses.Response غير مستورد"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: supervisor.sh
# ═══════════════════════════════════════════════════════════════════════════════

class TestR4SupervisorSh:
    """التحقق من وجود launch_research_agent في supervisor.sh."""

    def test_launch_function_exists(self) -> None:
        content = SUPERVISOR.read_text()
        assert "launch_research_agent" in content, "launch_research_agent مفقود من supervisor.sh"

    def test_port_8007(self) -> None:
        content = SUPERVISOR.read_text()
        assert "8007" in content, "المنفذ 8007 مفقود من supervisor.sh"

    def test_step_4g_comment(self) -> None:
        content = SUPERVISOR.read_text()
        assert "STEP 4G" in content or "4G" in content, "STEP 4G comment مفقود"

    def test_tavily_api_key_injected(self) -> None:
        content = SUPERVISOR.read_text()
        assert "TAVILY_API_KEY" in content, "TAVILY_API_KEY غير محقون في supervisor.sh"

    def test_asyncpg_conversion(self) -> None:
        content = SUPERVISOR.read_text()
        assert "asyncpg" in content, "asyncpg URL conversion مفقود من supervisor.sh"


# ═══════════════════════════════════════════════════════════════════════════════
# R5: automations.yaml
# ═══════════════════════════════════════════════════════════════════════════════

class TestR5AutomationsYaml:
    """التحقق من وجود research-agent في automations.yaml."""

    def test_service_defined(self) -> None:
        content = AUTOMATIONS.read_text()
        assert "research-agent:" in content, "research-agent service مفقود من automations.yaml"

    def test_port_8007_in_service(self) -> None:
        content = AUTOMATIONS.read_text()
        assert "8007" in content, "المنفذ 8007 مفقود من automations.yaml"

    def test_verify_task_exists(self) -> None:
        content = AUTOMATIONS.read_text()
        assert "verify-step7-research-agent" in content, "verify task مفقود"

    def test_restart_task_exists(self) -> None:
        content = AUTOMATIONS.read_text()
        assert "restart-research-agent" in content, "restart task مفقود"

    def test_run_tests_task_exists(self) -> None:
        content = AUTOMATIONS.read_text()
        assert "run-step7-tests" in content, "run-step7-tests task مفقود"

    def test_tavily_in_service_start(self) -> None:
        content = AUTOMATIONS.read_text()
        assert "TAVILY_API_KEY" in content, "TAVILY_API_KEY غير محقون في automations.yaml"

    def test_ready_command_checks_metrics(self) -> None:
        content = AUTOMATIONS.read_text()
        assert "cogniforge_research_startup" in content, "ready command لا يتحقق من metrics"


# ═══════════════════════════════════════════════════════════════════════════════
# R6: prometheus.yml
# ═══════════════════════════════════════════════════════════════════════════════

class TestR6PrometheusYml:
    """التحقق من وجود scrape target لـ research-agent في prometheus.yml."""

    def test_research_agent_job_exists(self) -> None:
        content = PROMETHEUS_YML.read_text()
        assert "research-agent" in content, "research-agent job مفقود من prometheus.yml"

    def test_port_8007_in_targets(self) -> None:
        content = PROMETHEUS_YML.read_text()
        assert "8007" in content, "المنفذ 8007 مفقود من prometheus.yml"

    def test_step_7_label(self) -> None:
        content = PROMETHEUS_YML.read_text()
        assert 'step: "7"' in content, 'label step: "7" مفقود من prometheus.yml'

    def test_metrics_path(self) -> None:
        content = PROMETHEUS_YML.read_text()
        assert "metrics_path: /metrics" in content, "metrics_path مفقود"


# ═══════════════════════════════════════════════════════════════════════════════
# R7: Grafana dashboard
# ═══════════════════════════════════════════════════════════════════════════════

class TestR7GrafanaDashboard:
    """التحقق من صحة Grafana dashboard."""

    def _load(self) -> dict:
        return json.loads(DASHBOARD.read_text())

    def test_file_exists(self) -> None:
        assert DASHBOARD.exists(), "Dashboard file مفقود"

    def test_uid_correct(self) -> None:
        d = self._load()
        assert d["uid"] == "cogniforge-ms-step7-research-agent", f"UID خاطئ: {d['uid']}"

    def test_has_step7_tag(self) -> None:
        d = self._load()
        assert "step7" in d.get("tags", []), "tag step7 مفقود"

    def test_refresh_10s(self) -> None:
        d = self._load()
        assert d.get("refresh") == "10s", "refresh ليس 10s"

    def test_has_enough_panels(self) -> None:
        d = self._load()
        assert len(d.get("panels", [])) >= 15, f"عدد panels غير كافٍ: {len(d['panels'])}"

    def test_has_tavily_panel(self) -> None:
        d = self._load()
        titles = [p.get("title", "") for p in d["panels"]]
        assert any("Tavily" in t for t in titles), "لا يوجد panel للـ Tavily"

    def test_has_search_panel(self) -> None:
        d = self._load()
        titles = [p.get("title", "") for p in d["panels"]]
        assert any("Search" in t for t in titles), "لا يوجد panel للـ Search"

    def test_has_health_matrix(self) -> None:
        d = self._load()
        titles = [p.get("title", "") for p in d["panels"]]
        assert any("Health" in t or "UP/DOWN" in t for t in titles), "لا يوجد health matrix panel"

    def test_has_startup_info_panel(self) -> None:
        d = self._load()
        titles = [p.get("title", "") for p in d["panels"]]
        assert any("Startup" in t or "startup" in t for t in titles), "لا يوجد startup info panel"

    def test_queries_reference_research_metrics(self) -> None:
        content = DASHBOARD.read_text()
        assert "cogniforge_research" in content, "لا توجد queries تشير إلى cogniforge_research_*"


# ═══════════════════════════════════════════════════════════════════════════════
# R8: unit tests للـ prom_metrics functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestR8PromMetricsFunctions:
    """اختبارات وحدة لدوال prom_metrics."""

    def test_import_prom_metrics(self) -> None:
        """يجب أن يُستورَد prom_metrics بدون أخطاء."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics", PROM_METRICS)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert hasattr(mod, "export_prometheus_text")
        assert hasattr(mod, "set_startup_info")
        assert hasattr(mod, "record_search")
        assert hasattr(mod, "record_tavily_call")
        assert hasattr(mod, "record_tavily_error")
        assert hasattr(mod, "record_deep_research")
        assert hasattr(mod, "record_http_request")
        assert hasattr(mod, "record_db_operation")
        assert hasattr(mod, "set_active_connections")
        assert hasattr(mod, "get_request_timer")
        assert hasattr(mod, "elapsed_since")

    def test_export_returns_bytes_and_str(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8a", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        body, ct = mod.export_prometheus_text()
        assert isinstance(body, bytes), "export_prometheus_text يجب أن يُعيد bytes"
        assert isinstance(ct, str), "content_type يجب أن يكون str"

    def test_set_startup_info_no_error(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8b", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.set_startup_info("1.0.0", "testing", "sqlite", "false")

    def test_record_search_no_error(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8c", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.record_search("db", "success", 0.05)
        mod.record_search("deep", "error", 2.5)

    def test_record_tavily_call_no_error(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8d", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.record_tavily_call("success")
        mod.record_tavily_call("error")
        mod.record_tavily_call("unavailable")

    def test_record_tavily_error_no_error(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8e", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.record_tavily_error("timeout")
        mod.record_tavily_error("rate_limit")
        mod.record_tavily_error("api_error")

    def test_record_deep_research_no_error(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8f", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.record_deep_research("success")
        mod.record_deep_research("error")

    def test_record_http_request_no_error(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8g", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.record_http_request("GET", "/health", 200, 0.01)
        mod.record_http_request("POST", "/execute", 500, 1.5)

    def test_record_db_operation_no_error(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8h", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.record_db_operation("select", "success", 0.005)
        mod.record_db_operation("insert", "error", 0.1)

    def test_timer_functions(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8i", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        t = mod.get_request_timer()
        time.sleep(0.01)
        elapsed = mod.elapsed_since(t)
        assert elapsed >= 0.01, f"elapsed_since يجب أن يكون >= 0.01، حصلنا على {elapsed}"

    def test_set_active_connections_no_error(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8j", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.set_active_connections(0)
        mod.set_active_connections(5)

    def test_export_contains_metric_names_after_calls(self) -> None:
        """بعد استدعاء set_startup_info، يجب أن يظهر المقياس في الإخراج."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_r8k", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.set_startup_info("1.0.0", "testing", "sqlite", "false")
        body, _ = mod.export_prometheus_text()
        text = body.decode()
        assert "cogniforge_research" in text, "المقاييس لا تظهر في الإخراج"
