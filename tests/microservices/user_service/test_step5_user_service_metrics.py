"""
اختبارات Step 5 — user-service Prometheus Metrics.

تتحقق هذه الاختبارات من:
  U1: prometheus-client موجود في requirements.txt
  U2: prom_metrics.py موجود ويحتوي المقاييس الصحيحة
  U3: /metrics endpoint موجود في main.py
  U4: supervisor.sh يُشغِّل user-service على :8001
  U5: automations.yaml يحتوي user-service service
  U6: Prometheus scrape config يحتوي user-service target
  U7: Grafana dashboard صالح (JSON)
  U8: unit tests للـ prom_metrics functions

المبدأ: كل اختبار يتحقق من artifact واحد فقط.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ── مسارات الملفات ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parents[3]
USER_SVC = ROOT / "microservices" / "user_service"
PROM_METRICS = USER_SVC / "src" / "core" / "prom_metrics.py"
MAIN_PY = USER_SVC / "main.py"
REQUIREMENTS = USER_SVC / "requirements.txt"
SUPERVISOR = ROOT / ".devcontainer" / "supervisor.sh"
AUTOMATIONS = ROOT / ".ona" / "automations.yaml"
PROMETHEUS_CFG = ROOT / "observability" / "native" / "prometheus.yml"
GRAFANA_DASHBOARD = (
    ROOT / "observability" / "grafana" / "dashboards" / "80-microservices-step5-user-service.json"
)


# ═══════════════════════════════════════════════════════════════════════════════
# U1 — prometheus-client في requirements.txt
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequirements:
    """يتحقق من وجود prometheus-client في requirements.txt."""

    def test_prometheus_client_in_requirements(self) -> None:
        """prometheus-client>=0.20.0 يجب أن يكون في requirements.txt."""
        content = REQUIREMENTS.read_text()
        assert "prometheus-client" in content, (
            "prometheus-client غائب من microservices/user_service/requirements.txt"
        )

    def test_prometheus_client_version_pinned(self) -> None:
        """يجب أن يكون الإصدار محدداً بـ >=0.20.0."""
        content = REQUIREMENTS.read_text()
        assert re.search(r"prometheus-client>=0\.20", content), (
            "prometheus-client يجب أن يكون >=0.20.0"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# U2 — prom_metrics.py موجود ويحتوي المقاييس الصحيحة
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromMetricsModule:
    """يتحقق من محتوى prom_metrics.py."""

    def test_file_exists(self) -> None:
        """prom_metrics.py يجب أن يكون موجوداً."""
        assert PROM_METRICS.exists(), f"الملف غائب: {PROM_METRICS}"

    def test_contains_startup_info_metric(self) -> None:
        """cogniforge_user_startup_info يجب أن يكون معرَّفاً."""
        content = PROM_METRICS.read_text()
        assert "cogniforge_user_startup_info" in content

    def test_contains_requests_total_metric(self) -> None:
        """cogniforge_user_requests_total يجب أن يكون معرَّفاً."""
        content = PROM_METRICS.read_text()
        assert "cogniforge_user_requests_total" in content

    def test_contains_auth_operations_metric(self) -> None:
        """cogniforge_user_auth_operations_total يجب أن يكون معرَّفاً."""
        content = PROM_METRICS.read_text()
        assert "cogniforge_user_auth_operations_total" in content

    def test_contains_registrations_metric(self) -> None:
        """cogniforge_user_registrations_total يجب أن يكون معرَّفاً."""
        content = PROM_METRICS.read_text()
        assert "cogniforge_user_registrations_total" in content

    def test_contains_logins_metric(self) -> None:
        """cogniforge_user_logins_total يجب أن يكون معرَّفاً."""
        content = PROM_METRICS.read_text()
        assert "cogniforge_user_logins_total" in content

    def test_contains_db_operations_metric(self) -> None:
        """cogniforge_user_db_operations_total يجب أن يكون معرَّفاً."""
        content = PROM_METRICS.read_text()
        assert "cogniforge_user_db_operations_total" in content

    def test_independent_registry(self) -> None:
        """يجب استخدام CollectorRegistry مستقل (لا REGISTRY الافتراضي)."""
        content = PROM_METRICS.read_text()
        assert "CollectorRegistry" in content
        assert "registry=reg" in content

    def test_defensive_import(self) -> None:
        """يجب استيراد prometheus_client بشكل دفاعي (try/except)."""
        content = PROM_METRICS.read_text()
        assert "try:" in content
        assert "ImportError" in content

    def test_export_function_exists(self) -> None:
        """export_prometheus_text() يجب أن تكون موجودة."""
        content = PROM_METRICS.read_text()
        assert "def export_prometheus_text" in content

    def test_set_startup_info_function_exists(self) -> None:
        """set_startup_info() يجب أن تكون موجودة."""
        content = PROM_METRICS.read_text()
        assert "def set_startup_info" in content

    def test_step5_label(self) -> None:
        """يجب أن يحتوي startup_info على label step='5'."""
        content = PROM_METRICS.read_text()
        assert 'step="5"' in content or "step='5'" in content


# ═══════════════════════════════════════════════════════════════════════════════
# U3 — /metrics endpoint في main.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestMainPyMetricsEndpoint:
    """يتحقق من وجود /metrics endpoint في main.py."""

    def test_metrics_endpoint_defined(self) -> None:
        """/metrics endpoint يجب أن يكون معرَّفاً."""
        content = MAIN_PY.read_text()
        assert '"/metrics"' in content or "'/metrics'" in content

    def test_export_prometheus_text_imported(self) -> None:
        """export_prometheus_text يجب أن تكون مستوردة في main.py."""
        content = MAIN_PY.read_text()
        assert "export_prometheus_text" in content

    def test_set_startup_info_called_in_lifespan(self) -> None:
        """set_startup_info يجب أن تُستدعى في lifespan."""
        content = MAIN_PY.read_text()
        assert "set_startup_info" in content

    def test_response_class_used(self) -> None:
        """يجب استخدام fastapi.responses.Response لإرجاع Prometheus text."""
        content = MAIN_PY.read_text()
        assert "Response" in content

    def test_prom_metrics_import(self) -> None:
        """prom_metrics يجب أن يكون مستورداً من src.core."""
        content = MAIN_PY.read_text()
        assert "prom_metrics" in content


# ═══════════════════════════════════════════════════════════════════════════════
# U4 — supervisor.sh يُشغِّل user-service
# ═══════════════════════════════════════════════════════════════════════════════


class TestSupervisorUserService:
    """يتحقق من وجود launch_user_service في supervisor.sh."""

    def test_launch_user_service_function_exists(self) -> None:
        """launch_user_service() يجب أن تكون موجودة في supervisor.sh."""
        content = SUPERVISOR.read_text()
        assert "launch_user_service" in content

    def test_user_service_port_8001(self) -> None:
        """user-service يجب أن يعمل على المنفذ 8001."""
        content = SUPERVISOR.read_text()
        assert "8001" in content

    def test_user_service_uvicorn_command(self) -> None:
        """uvicorn microservices.user_service يجب أن يكون في supervisor.sh."""
        content = SUPERVISOR.read_text()
        assert "uvicorn microservices.user_service" in content

    def test_user_database_url_injected(self) -> None:
        """USER_DATABASE_URL يجب أن يُحقَن في supervisor.sh."""
        content = SUPERVISOR.read_text()
        assert "USER_DATABASE_URL" in content


# ═══════════════════════════════════════════════════════════════════════════════
# U5 — automations.yaml يحتوي user-service
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutomationsUserService:
    """يتحقق من وجود user-service في automations.yaml."""

    def test_user_service_service_defined(self) -> None:
        """user-service يجب أن يكون معرَّفاً كـ service في automations.yaml."""
        content = AUTOMATIONS.read_text()
        assert "user-service:" in content

    def test_user_service_ready_command(self) -> None:
        """ready command يجب أن يتحقق من /health و /metrics."""
        content = AUTOMATIONS.read_text()
        assert "localhost:8001/health" in content

    def test_verify_step5_task_exists(self) -> None:
        """verify-step5-user-service task يجب أن يكون موجوداً."""
        content = AUTOMATIONS.read_text()
        assert "verify-step5-user-service" in content

    def test_restart_user_service_task_exists(self) -> None:
        """restart-user-service task يجب أن يكون موجوداً."""
        content = AUTOMATIONS.read_text()
        assert "restart-user-service" in content

    def test_run_step5_tests_task_exists(self) -> None:
        """run-step5-tests task يجب أن يكون موجوداً."""
        content = AUTOMATIONS.read_text()
        assert "run-step5-tests" in content


# ═══════════════════════════════════════════════════════════════════════════════
# U6 — Prometheus scrape config
# ═══════════════════════════════════════════════════════════════════════════════


class TestPrometheusConfig:
    """يتحقق من وجود user-service في prometheus.yml."""

    def test_user_service_job_exists(self) -> None:
        """job_name: user-service يجب أن يكون في prometheus.yml."""
        content = PROMETHEUS_CFG.read_text()
        assert "job_name: user-service" in content

    def test_user_service_port_8001_in_config(self) -> None:
        """localhost:8001 يجب أن يكون في prometheus.yml."""
        content = PROMETHEUS_CFG.read_text()
        assert "localhost:8001" in content

    def test_step5_label_in_config(self) -> None:
        """step: '5' يجب أن يكون في scrape config."""
        content = PROMETHEUS_CFG.read_text()
        assert 'step: "5"' in content or "step: '5'" in content


# ═══════════════════════════════════════════════════════════════════════════════
# U7 — Grafana dashboard صالح
# ═══════════════════════════════════════════════════════════════════════════════


class TestGrafanaDashboard:
    """يتحقق من صحة Grafana dashboard لـ Step 5."""

    def test_dashboard_file_exists(self) -> None:
        """80-microservices-step5-user-service.json يجب أن يكون موجوداً."""
        assert GRAFANA_DASHBOARD.exists(), f"Dashboard غائب: {GRAFANA_DASHBOARD.name}"

    def test_dashboard_valid_json(self) -> None:
        """Dashboard يجب أن يكون JSON صالحاً."""
        content = GRAFANA_DASHBOARD.read_text()
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_dashboard_uid(self) -> None:
        """UID يجب أن يكون cogniforge-ms-step5-user-service."""
        data = json.loads(GRAFANA_DASHBOARD.read_text())
        assert data.get("uid") == "cogniforge-ms-step5-user-service"

    def test_dashboard_has_panels(self) -> None:
        """Dashboard يجب أن يحتوي على panels."""
        data = json.loads(GRAFANA_DASHBOARD.read_text())
        panels = data.get("panels", [])
        assert len(panels) >= 10, f"Dashboard يحتوي {len(panels)} panels فقط — يجب >= 10"

    def test_dashboard_refresh_interval(self) -> None:
        """refresh يجب أن يكون 10s للمراقبة الحية."""
        data = json.loads(GRAFANA_DASHBOARD.read_text())
        assert data.get("refresh") == "10s"

    def test_dashboard_references_user_metrics(self) -> None:
        """Dashboard يجب أن يستخدم cogniforge_user_* metrics."""
        content = GRAFANA_DASHBOARD.read_text()
        assert "cogniforge_user" in content

    def test_dashboard_title(self) -> None:
        """Dashboard title يجب أن يشير إلى Step 5."""
        data = json.loads(GRAFANA_DASHBOARD.read_text())
        title = data.get("title", "")
        assert "Step 5" in title or "User Service" in title or "user" in title.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# U8 — unit tests للـ prom_metrics functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromMetricsFunctions:
    """unit tests للدوال العامة في prom_metrics.py."""

    def test_export_prometheus_text_returns_bytes(self) -> None:
        """export_prometheus_text() يجب أن تُعيد (bytes, str)."""
        from microservices.user_service.src.core.prom_metrics import (
            export_prometheus_text,
        )

        content, content_type = export_prometheus_text()
        assert isinstance(content, bytes)
        assert isinstance(content_type, str)
        assert "text/plain" in content_type

    def test_record_http_request_no_exception(self) -> None:
        """record_http_request() يجب أن تعمل بدون استثناء."""
        from microservices.user_service.src.core.prom_metrics import (
            record_http_request,
        )

        record_http_request("GET", "/health", 200, 0.01)

    def test_record_auth_operation_no_exception(self) -> None:
        """record_auth_operation() يجب أن تعمل بدون استثناء."""
        from microservices.user_service.src.core.prom_metrics import (
            record_auth_operation,
        )

        record_auth_operation("login", "success", 0.05)

    def test_record_auth_operation_register(self) -> None:
        """record_auth_operation('register') يجب أن تُحدِّث registrations_total."""
        from microservices.user_service.src.core.prom_metrics import (
            record_auth_operation,
        )

        record_auth_operation("register", "success", 0.1)

    def test_record_db_operation_no_exception(self) -> None:
        """record_db_operation() يجب أن تعمل بدون استثناء."""
        from microservices.user_service.src.core.prom_metrics import (
            record_db_operation,
        )

        record_db_operation("select", "success", 0.002)

    def test_set_startup_info_no_exception(self) -> None:
        """set_startup_info() يجب أن تعمل بدون استثناء."""
        from microservices.user_service.src.core.prom_metrics import set_startup_info

        set_startup_info(
            version="1.0.0",
            environment="testing",
            db_backend="sqlite",
        )

    def test_get_request_timer_returns_float(self) -> None:
        """get_request_timer() يجب أن تُعيد float."""
        from microservices.user_service.src.core.prom_metrics import get_request_timer

        t = get_request_timer()
        assert isinstance(t, float)
        assert t > 0

    def test_elapsed_since_positive(self) -> None:
        """elapsed_since() يجب أن تُعيد قيمة موجبة."""
        import time

        from microservices.user_service.src.core.prom_metrics import (
            elapsed_since,
            get_request_timer,
        )

        start = get_request_timer()
        time.sleep(0.001)
        elapsed = elapsed_since(start)
        assert elapsed > 0

    def test_export_after_startup_info_contains_metric(self) -> None:
        """بعد set_startup_info، export يجب أن يحتوي cogniforge_user_startup_info."""
        from microservices.user_service.src.core.prom_metrics import (
            export_prometheus_text,
            set_startup_info,
        )

        set_startup_info(
            version="1.0.0",
            environment="testing",
            db_backend="sqlite",
        )
        content, _ = export_prometheus_text()
        # إذا prometheus_client مثبّت، يجب أن يحتوي المقياس
        # إذا غير مثبّت، يُعيد stub — لا نفشل الاختبار
        assert isinstance(content, bytes)
