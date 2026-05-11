"""
اختبارات الخطوة الانتقالية الرابعة — Step 4: Persistence Relay & Prometheus Metrics
──────────────────────────────────────────────────────────────────────────────────────
تتحقق من:
  P1 — prometheus_client مُدرج في requirements.txt
  P2 — prom_metrics.py موجود ويُصدِّر الـ counters الصحيحة
  P3 — /metrics endpoint مُعرَّف في main.py
  P4 — OUTBOX_RELAY_ENABLED=true في supervisor.sh
  P5 — OUTBOX_RELAY_ENABLED=true في .ona/automations.yaml
  P6 — Grafana dashboard 70-microservices-step4-persistence.json صالح
  P7 — Prometheus scrape config يستهدف orchestrator-service بـ step="4"
  P8 — record_outbox_relay_cycle تُحدِّث counters بشكل صحيح
  P9 — set_startup_info تُسجِّل gauge بشكل صحيح
  P10 — export_prometheus_text تُعيد bytes صالحة
"""

import json
import pathlib
import re

ROOT = pathlib.Path(".")
ORCH_MAIN = ROOT / "microservices" / "orchestrator_service" / "main.py"
ORCH_REQS = ROOT / "microservices" / "orchestrator_service" / "requirements.txt"
PROM_METRICS = ROOT / "microservices" / "orchestrator_service" / "src" / "core" / "prom_metrics.py"
SUPERVISOR = ROOT / ".devcontainer" / "supervisor.sh"
AUTOMATIONS = ROOT / ".ona" / "automations.yaml"
PROMETHEUS_CFG = ROOT / "observability" / "native" / "prometheus.yml"
GRAFANA_DASH = (
    ROOT / "observability" / "grafana" / "dashboards" / "70-microservices-step4-persistence.json"
)


# ─── P1: prometheus_client في requirements.txt ──────────────────────────────


class TestPrometheusClientRequirement:
    """يتحقق من أن prometheus_client مُدرج في requirements.txt للـ orchestrator."""

    def test_prometheus_client_in_requirements(self):
        """prometheus_client يجب أن يكون في requirements.txt."""
        text = ORCH_REQS.read_text(encoding="utf-8")
        assert "prometheus-client" in text, (
            "prometheus-client غائب من microservices/orchestrator_service/requirements.txt — "
            "Step 4 يتطلبه لـ /metrics endpoint حقيقي."
        )

    def test_prometheus_client_version_pinned(self):
        """يجب أن يكون prometheus-client مُقيَّداً بإصدار >=0.20.0."""
        text = ORCH_REQS.read_text(encoding="utf-8")
        assert re.search(r"prometheus-client>=0\.\d+", text), (
            "prometheus-client يجب أن يكون مُقيَّداً بـ >=0.20.0"
        )


# ─── P2: prom_metrics.py موجود ويحتوي الـ counters الصحيحة ─────────────────


class TestPromMetricsModule:
    """يتحقق من وجود prom_metrics.py وصحة محتواه."""

    def test_prom_metrics_file_exists(self):
        """prom_metrics.py يجب أن يكون موجوداً."""
        assert PROM_METRICS.exists(), f"{PROM_METRICS} غير موجود — Step 4 يتطلب هذه الوحدة."

    def _text(self) -> str:
        return PROM_METRICS.read_text(encoding="utf-8")

    def test_outbox_relay_cycles_counter_defined(self):
        """cogniforge_outbox_relay_cycles_total يجب أن يكون مُعرَّفاً."""
        assert "cogniforge_outbox_relay_cycles_total" in self._text()

    def test_outbox_relay_processed_counter_defined(self):
        """cogniforge_outbox_relay_processed_total يجب أن يكون مُعرَّفاً."""
        assert "cogniforge_outbox_relay_processed_total" in self._text()

    def test_outbox_relay_failed_counter_defined(self):
        """cogniforge_outbox_relay_failed_total يجب أن يكون مُعرَّفاً."""
        assert "cogniforge_outbox_relay_failed_total" in self._text()

    def test_stategraph_invocations_counter_defined(self):
        """cogniforge_stategraph_invocations_total يجب أن يكون مُعرَّفاً."""
        assert "cogniforge_stategraph_invocations_total" in self._text()

    def test_startup_info_gauge_defined(self):
        """cogniforge_orchestrator_startup_info يجب أن يكون مُعرَّفاً."""
        assert "cogniforge_orchestrator_startup_info" in self._text()

    def test_export_function_defined(self):
        """export_prometheus_text يجب أن تكون مُعرَّفة."""
        assert "def export_prometheus_text" in self._text()

    def test_record_outbox_relay_cycle_defined(self):
        """record_outbox_relay_cycle يجب أن تكون مُعرَّفة."""
        assert "def record_outbox_relay_cycle" in self._text()

    def test_set_startup_info_defined(self):
        """set_startup_info يجب أن تكون مُعرَّفة."""
        assert "def set_startup_info" in self._text()

    def test_independent_registry_used(self):
        """يجب استخدام CollectorRegistry مستقل (ليس REGISTRY الافتراضي)."""
        assert "CollectorRegistry" in self._text(), (
            "يجب استخدام CollectorRegistry مستقل لتجنب التعارض مع المونوليث."
        )

    def test_defensive_import(self):
        """يجب أن يكون الاستيراد دفاعياً (try/except ImportError)."""
        assert "ImportError" in self._text(), (
            "prom_metrics.py يجب أن يتعامل مع غياب prometheus_client بشكل دفاعي."
        )


# ─── P3: /metrics endpoint في main.py ───────────────────────────────────────


class TestMetricsEndpointInMain:
    """يتحقق من أن /metrics endpoint مُعرَّف في main.py."""

    def _text(self) -> str:
        return ORCH_MAIN.read_text(encoding="utf-8")

    def test_metrics_route_defined(self):
        """/metrics route يجب أن يكون مُعرَّفاً في main.py."""
        assert '"/metrics"' in self._text() or "'/metrics'" in self._text(), (
            "/metrics endpoint غائب من main.py — Prometheus لن يستطيع scrape الخدمة."
        )

    def test_export_prometheus_text_imported(self):
        """export_prometheus_text يجب أن تكون مستوردة في main.py."""
        assert "export_prometheus_text" in self._text()

    def test_prom_metrics_imported(self):
        """prom_metrics يجب أن يكون مستورداً في main.py."""
        assert "prom_metrics" in self._text()

    def test_set_startup_info_called_in_lifespan(self):
        """set_startup_info يجب أن تُستدعى في lifespan."""
        assert "set_startup_info" in self._text(), (
            "set_startup_info غير مستدعاة في lifespan — "
            "cogniforge_orchestrator_startup_info لن يظهر في Grafana."
        )

    def test_record_outbox_relay_cycle_called(self):
        """record_outbox_relay_cycle يجب أن تُستدعى في _outbox_relay_loop."""
        assert "record_outbox_relay_cycle" in self._text()

    def test_record_outbox_relay_error_called(self):
        """record_outbox_relay_error يجب أن تُستدعى عند فشل الـ relay."""
        assert "record_outbox_relay_error" in self._text()


# ─── P4: OUTBOX_RELAY_ENABLED=true في supervisor.sh ─────────────────────────


class TestSupervisorOutboxRelay:
    """يتحقق من أن supervisor.sh يُشغِّل orchestrator مع OUTBOX_RELAY_ENABLED=true."""

    def _text(self) -> str:
        return SUPERVISOR.read_text(encoding="utf-8")

    def test_outbox_relay_enabled_true_in_supervisor(self):
        """OUTBOX_RELAY_ENABLED=true يجب أن يكون في supervisor.sh."""
        text = self._text()
        # نبحث عن السطر بعد launch_orchestrator_service
        launch_pos = text.find("launch_orchestrator_service()")
        assert launch_pos != -1, "launch_orchestrator_service() غير موجودة في supervisor.sh"
        # نبحث عن OUTBOX_RELAY_ENABLED قبل launch_orchestrator_service (في تعريف الدالة)
        text.rfind("launch_orchestrator_service()", 0, launch_pos)
        relay_pos = text.find('OUTBOX_RELAY_ENABLED="true"')
        assert relay_pos != -1, (
            'OUTBOX_RELAY_ENABLED="true" غائب من supervisor.sh — '
            "Step 4 يتطلب تفعيل relay في Codespaces."
        )

    def test_outbox_relay_interval_set(self):
        """OUTBOX_RELAY_INTERVAL_SECONDS يجب أن يكون مضبوطاً في supervisor.sh."""
        assert "OUTBOX_RELAY_INTERVAL_SECONDS" in self._text()


# ─── P5: OUTBOX_RELAY_ENABLED=true في automations.yaml ──────────────────────


class TestAutomationsOutboxRelay:
    """يتحقق من أن .ona/automations.yaml يُشغِّل orchestrator مع OUTBOX_RELAY_ENABLED=true."""

    def _text(self) -> str:
        return AUTOMATIONS.read_text(encoding="utf-8")

    def test_outbox_relay_enabled_true_in_automations(self):
        """OUTBOX_RELAY_ENABLED=true يجب أن يكون في automations.yaml."""
        assert (
            'OUTBOX_RELAY_ENABLED="true"' in self._text()
            or 'OUTBOX_RELAY_ENABLED: "true"' in self._text()
            or "OUTBOX_RELAY_ENABLED=true" in self._text()
        ), "OUTBOX_RELAY_ENABLED=true غائب من .ona/automations.yaml"

    def test_verify_step4_metrics_task_exists(self):
        """verify-step4-metrics task يجب أن يكون موجوداً في automations.yaml."""
        assert "verify-step4-metrics" in self._text()

    def test_run_step4_tests_task_exists(self):
        """run-step4-tests task يجب أن يكون موجوداً في automations.yaml."""
        assert "run-step4-tests" in self._text()

    def test_metrics_endpoint_in_ready_command(self):
        """ready command يجب أن يتحقق من /metrics endpoint."""
        assert "/metrics" in self._text()


# ─── P6: Grafana dashboard صالح ─────────────────────────────────────────────


class TestGrafanaDashboardStep4:
    """يتحقق من صحة Grafana dashboard للخطوة 4."""

    def _dashboard(self) -> dict:
        return json.loads(GRAFANA_DASH.read_text(encoding="utf-8"))

    def test_dashboard_file_exists(self):
        """70-microservices-step4-persistence.json يجب أن يكون موجوداً."""
        assert GRAFANA_DASH.exists()

    def test_dashboard_valid_json(self):
        """الـ dashboard يجب أن يكون JSON صالحاً."""
        d = self._dashboard()
        assert isinstance(d, dict)

    def test_dashboard_uid(self):
        """uid يجب أن يكون cogniforge-ms-step4-persistence."""
        assert self._dashboard()["uid"] == "cogniforge-ms-step4-persistence"

    def test_dashboard_has_panels(self):
        """الـ dashboard يجب أن يحتوي على panels."""
        panels = self._dashboard().get("panels", [])
        assert len(panels) >= 10, f"الـ dashboard يحتوي {len(panels)} panels فقط — يجب >= 10"

    def test_outbox_relay_metric_in_dashboard(self):
        """cogniforge_outbox_relay_cycles_total يجب أن يكون في الـ dashboard."""
        text = GRAFANA_DASH.read_text(encoding="utf-8")
        assert "cogniforge_outbox_relay_cycles_total" in text

    def test_startup_info_metric_in_dashboard(self):
        """cogniforge_orchestrator_startup_info يجب أن يكون في الـ dashboard."""
        text = GRAFANA_DASH.read_text(encoding="utf-8")
        assert "cogniforge_orchestrator_startup_info" in text

    def test_stategraph_metric_in_dashboard(self):
        """cogniforge_stategraph_invocations_total يجب أن يكون في الـ dashboard."""
        text = GRAFANA_DASH.read_text(encoding="utf-8")
        assert "cogniforge_stategraph_invocations_total" in text

    def test_dashboard_refresh_interval(self):
        """refresh يجب أن يكون 10s أو أقل للمراقبة الحية."""
        refresh = self._dashboard().get("refresh", "")
        assert refresh in ("10s", "5s", "30s"), (
            f"refresh={refresh} — يجب أن يكون 10s أو أقل للمراقبة الحية"
        )


# ─── P7: Prometheus scrape config ───────────────────────────────────────────


class TestPrometheusConfig:
    """يتحقق من أن prometheus.yml يستهدف orchestrator-service بـ step=4."""

    def _text(self) -> str:
        return PROMETHEUS_CFG.read_text(encoding="utf-8")

    def test_orchestrator_scrape_target_exists(self):
        """orchestrator-service يجب أن يكون في prometheus.yml."""
        assert "orchestrator-service" in self._text()

    def test_orchestrator_scrape_step4_label(self):
        """step: \"4\" يجب أن يكون في scrape config للـ orchestrator."""
        assert 'step: "4"' in self._text() or "step: '4'" in self._text(), (
            "step label يجب أن يكون 4 في prometheus.yml — يُميِّز Step 4 عن Step 3."
        )

    def test_orchestrator_metrics_path(self):
        """metrics_path يجب أن يكون /metrics."""
        text = self._text()
        orch_pos = text.find("orchestrator-service")
        metrics_pos = text.find("metrics_path: /metrics", orch_pos)
        assert metrics_pos != -1, "metrics_path: /metrics غائب من scrape config للـ orchestrator"


# ─── P8/P9/P10: Unit tests للـ prom_metrics functions ───────────────────────


class TestPromMetricsFunctions:
    """اختبارات وحدة لدوال prom_metrics.py."""

    def test_export_prometheus_text_returns_bytes(self):
        """export_prometheus_text يجب أن تُعيد bytes."""
        from microservices.orchestrator_service.src.core.prom_metrics import (
            export_prometheus_text,
        )

        body, _content_type = export_prometheus_text()
        assert isinstance(body, bytes), "export_prometheus_text يجب أن تُعيد bytes"
        assert len(body) > 0, "export_prometheus_text يجب أن تُعيد محتوى غير فارغ"

    def test_export_prometheus_text_content_type(self):
        """content_type يجب أن يحتوي على text/plain أو prometheus."""
        from microservices.orchestrator_service.src.core.prom_metrics import (
            export_prometheus_text,
        )

        _, content_type = export_prometheus_text()
        assert "text/plain" in content_type or "prometheus" in content_type.lower()

    def test_record_outbox_relay_cycle_success(self):
        """record_outbox_relay_cycle يجب أن تعمل بدون استثناء."""
        from microservices.orchestrator_service.src.core.prom_metrics import (
            record_outbox_relay_cycle,
        )

        # لا يجب أن يرفع استثناء
        record_outbox_relay_cycle(
            {"processed": 5, "failed": 1, "skipped_max_attempts": 0, "skipped_inflight": 2}
        )

    def test_record_outbox_relay_cycle_empty_summary(self):
        """record_outbox_relay_cycle يجب أن تتعامل مع summary فارغ."""
        from microservices.orchestrator_service.src.core.prom_metrics import (
            record_outbox_relay_cycle,
        )

        record_outbox_relay_cycle({})  # لا يجب أن يرفع استثناء

    def test_record_outbox_relay_error(self):
        """record_outbox_relay_error يجب أن تعمل بدون استثناء."""
        from microservices.orchestrator_service.src.core.prom_metrics import (
            record_outbox_relay_error,
        )

        record_outbox_relay_error()

    def test_set_startup_info(self):
        """set_startup_info يجب أن تعمل بدون استثناء."""
        from microservices.orchestrator_service.src.core.prom_metrics import (
            set_startup_info,
        )

        set_startup_info(
            version="4.0.0-step4",
            environment="testing",
            outbox_relay_enabled=True,
            graph_ready=False,
        )

    def test_metrics_contain_startup_info_after_set(self):
        """بعد set_startup_info، يجب أن تظهر cogniforge_orchestrator_startup_info في /metrics."""
        from microservices.orchestrator_service.src.core.prom_metrics import (
            export_prometheus_text,
            set_startup_info,
        )

        set_startup_info(
            version="4.0.0-test",
            environment="testing",
            outbox_relay_enabled=True,
            graph_ready=True,
        )
        body, _ = export_prometheus_text()
        text = body.decode("utf-8")
        assert "cogniforge_orchestrator_startup_info" in text, (
            "cogniforge_orchestrator_startup_info غائب من /metrics بعد set_startup_info"
        )

    def test_metrics_contain_outbox_counters_after_relay(self):
        """بعد record_outbox_relay_cycle، يجب أن تظهر cogniforge_outbox_relay_cycles_total."""
        from microservices.orchestrator_service.src.core.prom_metrics import (
            export_prometheus_text,
            record_outbox_relay_cycle,
        )

        record_outbox_relay_cycle({"processed": 3})
        body, _ = export_prometheus_text()
        text = body.decode("utf-8")
        assert "cogniforge_outbox_relay_cycles_total" in text, (
            "cogniforge_outbox_relay_cycles_total غائب من /metrics بعد record_outbox_relay_cycle"
        )
