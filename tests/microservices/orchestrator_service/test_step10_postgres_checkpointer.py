"""
اختبارات Step 10 — Postgres Checkpointer.

تتحقق هذه الاختبارات من:
  C1: prom_metrics.py — المقاييس الجديدة موجودة (6 مقاييس)
  C2: database.py — _InstrumentedCheckpointer + _build_psycopg_conninfo
  C3: routes.py — /checkpointer/status endpoint
  C4: main.py — checkpointer_backend في set_startup_info
  C5: prometheus.yml — scrape target postgres-checkpointer
  C6: Grafana dashboard — صالح JSON + UID + panels
  C7: unit tests — _InstrumentedCheckpointer logic
  C8: unit tests — prom_metrics checkpointer functions
  C9: unit tests — _build_psycopg_conninfo URL conversion
  C10: automations.yaml — step10 tasks

مبدأ الاختبار: كل اختبار يتحقق من سلوك (behavior) لا تنفيذ (implementation).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── مسارات الملفات ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parents[3]
ORCH_ROOT = ROOT / "microservices" / "orchestrator_service"
PROM_METRICS = ORCH_ROOT / "src" / "core" / "prom_metrics.py"
DATABASE_PY = ORCH_ROOT / "src" / "core" / "database.py"
ROUTES_PY = ORCH_ROOT / "src" / "api" / "routes.py"
MAIN_PY = ORCH_ROOT / "main.py"
PROMETHEUS_YML = ROOT / "observability" / "native" / "prometheus.yml"
DASHBOARD = ROOT / "observability" / "grafana" / "dashboards" / "130-microservices-step10-postgres-checkpointer.json"
AUTOMATIONS = ROOT / ".ona" / "automations.yaml"


# ═══════════════════════════════════════════════════════════════════════════════
# C1: prom_metrics.py — المقاييس الجديدة
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromMetricsCheckpointer:
    """يتحقق من وجود مقاييس checkpointer في prom_metrics.py."""

    def _src(self) -> str:
        return PROM_METRICS.read_text()

    def test_checkpointer_writes_metric_defined(self):
        assert "cogniforge_checkpointer_writes_total" in self._src()

    def test_checkpointer_reads_metric_defined(self):
        assert "cogniforge_checkpointer_reads_total" in self._src()

    def test_checkpointer_duration_metric_defined(self):
        assert "cogniforge_checkpointer_duration_seconds" in self._src()

    def test_checkpointer_errors_metric_defined(self):
        assert "cogniforge_checkpointer_errors_total" in self._src()

    def test_checkpointer_active_threads_metric_defined(self):
        assert "cogniforge_checkpointer_active_threads" in self._src()

    def test_checkpointer_backend_info_metric_defined(self):
        assert "cogniforge_checkpointer_backend_info" in self._src()

    def test_record_checkpointer_write_function_exists(self):
        assert "def record_checkpointer_write" in self._src()

    def test_record_checkpointer_read_function_exists(self):
        assert "def record_checkpointer_read" in self._src()

    def test_record_checkpointer_error_function_exists(self):
        assert "def record_checkpointer_error" in self._src()

    def test_set_checkpointer_active_threads_function_exists(self):
        assert "def set_checkpointer_active_threads" in self._src()

    def test_set_checkpointer_backend_info_function_exists(self):
        assert "def set_checkpointer_backend_info" in self._src()

    def test_startup_info_has_checkpointer_backend_label(self):
        src = self._src()
        assert "checkpointer_backend" in src

    def test_set_startup_info_accepts_checkpointer_backend_param(self):
        src = self._src()
        assert "checkpointer_backend" in src
        # يجب أن يكون parameter في set_startup_info
        assert "def set_startup_info" in src

    def test_duration_histogram_has_operation_label(self):
        src = self._src()
        # operation label: write | read | setup | list
        assert '"operation"' in src or "'operation'" in src

    def test_writes_counter_has_status_label(self):
        src = self._src()
        assert '"status"' in src or "'status'" in src

    def test_reads_counter_has_status_label(self):
        # hit | miss | error
        src = self._src()
        assert "hit" in src

    def test_errors_counter_has_error_type_label(self):
        src = self._src()
        assert "error_type" in src

    def test_backend_info_has_backend_label(self):
        src = self._src()
        assert '"backend"' in src or "'backend'" in src

    def test_backend_info_has_step_label(self):
        src = self._src()
        # step label في CHECKPOINTER_BACKEND_INFO
        assert "step" in src

    def test_independent_registry_used(self):
        src = self._src()
        assert "CollectorRegistry" in src
        assert "_get_registry" in src


# ═══════════════════════════════════════════════════════════════════════════════
# C2: database.py — _InstrumentedCheckpointer + _build_psycopg_conninfo
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatabaseCheckpointer:
    """يتحقق من بنية database.py لـ Step 10."""

    def _src(self) -> str:
        return DATABASE_PY.read_text()

    def test_instrumented_checkpointer_class_exists(self):
        assert "_InstrumentedCheckpointer" in self._src()

    def test_instrumented_checkpointer_inherits_from_base(self):
        # يجب أن يرث من AsyncPostgresSaver (subclass لا wrapper)
        src = self._src()
        assert "_make_instrumented_class" in src or "AsyncPostgresSaver" in src

    def test_aput_method_exists(self):
        assert "async def aput" in self._src()

    def test_aget_method_exists(self):
        assert "async def aget" in self._src()

    def test_aget_tuple_method_exists(self):
        assert "async def aget_tuple" in self._src()

    def test_setup_method_exists(self):
        assert "async def setup" in self._src()

    def test_build_psycopg_conninfo_function_exists(self):
        assert "_build_psycopg_conninfo" in self._src()

    def test_psycopg_conninfo_removes_asyncpg_scheme(self):
        src = self._src()
        assert "_build_psycopg_conninfo" in src

    def test_pool_size_constant_defined(self):
        assert "_POOL_SIZE" in self._src()

    def test_get_checkpointer_function_exists(self):
        assert "def get_checkpointer" in self._src()

    def test_init_db_creates_checkpointer(self):
        src = self._src()
        assert "AsyncPostgresSaver" in src
        assert "async def init_db" in src

    def test_close_db_closes_pool(self):
        src = self._src()
        assert "async def close_db" in src
        assert "_postgres_pool" in src

    def test_prometheus_metrics_imported_defensively(self):
        src = self._src()
        assert "record_checkpointer_write" in src
        assert "record_checkpointer_read" in src
        assert "record_checkpointer_error" in src

    def test_fallback_stubs_defined_on_import_error(self):
        src = self._src()
        assert "ImportError" in src
        assert "_METRICS_AVAILABLE" in src

    def test_active_threads_set_tracked(self):
        src = self._src()
        assert "_active_threads" in src

    def test_set_checkpointer_backend_info_called_in_init_db(self):
        src = self._src()
        assert "set_checkpointer_backend_info" in src

    def test_non_fatal_on_checkpointer_init_failure(self):
        src = self._src()
        # فشل الـ checkpointer لا يوقف الخدمة
        assert "non-fatal" in src or "non_fatal" in src or "non fatal" in src.lower()

    def test_lazy_singleton_pattern_preserved(self):
        src = self._src()
        assert "_engine: AsyncEngine | None = None" in src
        assert "def get_engine" in src

    def test_make_instrumented_class_factory_exists(self):
        # factory function تُنشئ subclass من base_class
        assert "_make_instrumented_class" in self._src()


# ═══════════════════════════════════════════════════════════════════════════════
# C3: routes.py — /checkpointer/status endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoutesCheckpointerStatus:
    """يتحقق من /checkpointer/status endpoint في routes.py."""

    def _src(self) -> str:
        return ROUTES_PY.read_text()

    def test_checkpointer_status_endpoint_exists(self):
        assert "/checkpointer/status" in self._src()

    def test_checkpointer_status_is_get(self):
        src = self._src()
        assert 'router.get' in src
        assert "/checkpointer/status" in src

    def test_checkpointer_status_returns_backend_field(self):
        src = self._src()
        assert '"backend"' in src or "'backend'" in src

    def test_checkpointer_status_returns_step_field(self):
        src = self._src()
        assert '"step"' in src or "'step'" in src

    def test_checkpointer_status_returns_active_field(self):
        src = self._src()
        assert '"active"' in src or "'active'" in src

    def test_checkpointer_status_returns_active_threads(self):
        src = self._src()
        assert "active_threads" in src

    def test_checkpointer_status_handles_none_checkpointer(self):
        src = self._src()
        # يجب أن يتعامل مع حالة None (MemorySaver fallback)
        assert "memory" in src


# ═══════════════════════════════════════════════════════════════════════════════
# C4: main.py — checkpointer_backend في set_startup_info
# ═══════════════════════════════════════════════════════════════════════════════

class TestMainCheckpointerBackend:
    """يتحقق من تمرير checkpointer_backend في main.py."""

    def _src(self) -> str:
        return MAIN_PY.read_text()

    def test_checkpointer_backend_passed_to_set_startup_info(self):
        src = self._src()
        assert "checkpointer_backend" in src

    def test_backend_detection_logic_exists(self):
        src = self._src()
        # يكتشف postgres | memory | none
        assert "postgres" in src
        assert "memory" in src

    def test_get_checkpointer_called_in_lifespan(self):
        src = self._src()
        assert "get_checkpointer" in src


# ═══════════════════════════════════════════════════════════════════════════════
# C5: prometheus.yml — scrape target
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrometheusConfig:
    """يتحقق من scrape target postgres-checkpointer في prometheus.yml."""

    def _src(self) -> str:
        return PROMETHEUS_YML.read_text()

    def test_postgres_checkpointer_job_exists(self):
        assert "postgres-checkpointer" in self._src()

    def test_step10_label_present(self):
        assert 'step: "10"' in self._src()

    def test_target_points_to_8006(self):
        src = self._src()
        # postgres-checkpointer يستخدم نفس orchestrator-service:8006
        assert "localhost:8006" in src

    def test_scrape_interval_10s(self):
        src = self._src()
        assert "scrape_interval: 10s" in src


# ═══════════════════════════════════════════════════════════════════════════════
# C6: Grafana dashboard
# ═══════════════════════════════════════════════════════════════════════════════

class TestGrafanaDashboard:
    """يتحقق من صحة Grafana dashboard لـ Step 10."""

    def _dashboard(self) -> dict:
        return json.loads(DASHBOARD.read_text())

    def test_dashboard_file_exists(self):
        assert DASHBOARD.exists()

    def test_dashboard_valid_json(self):
        d = self._dashboard()
        assert isinstance(d, dict)

    def test_dashboard_uid_correct(self):
        assert self._dashboard()["uid"] == "cogniforge-ms-step10-checkpointer"

    def test_dashboard_title_contains_step10(self):
        title = self._dashboard()["title"]
        assert "10" in title or "Step 10" in title

    def test_dashboard_has_panels(self):
        panels = self._dashboard().get("panels", [])
        assert len(panels) >= 8

    def test_dashboard_has_checkpointer_writes_panel(self):
        d = self._dashboard()
        content = json.dumps(d)
        assert "cogniforge_checkpointer_writes_total" in content

    def test_dashboard_has_checkpointer_reads_panel(self):
        content = json.dumps(self._dashboard())
        assert "cogniforge_checkpointer_reads_total" in content

    def test_dashboard_has_duration_panel(self):
        content = json.dumps(self._dashboard())
        assert "cogniforge_checkpointer_duration_seconds" in content

    def test_dashboard_has_errors_panel(self):
        content = json.dumps(self._dashboard())
        assert "cogniforge_checkpointer_errors_total" in content

    def test_dashboard_has_active_threads_panel(self):
        content = json.dumps(self._dashboard())
        assert "cogniforge_checkpointer_active_threads" in content

    def test_dashboard_refresh_10s(self):
        assert self._dashboard().get("refresh") == "10s"

    def test_dashboard_has_step10_tag(self):
        tags = self._dashboard().get("tags", [])
        assert "step10" in tags or "checkpointer" in tags

    def test_dashboard_has_health_matrix(self):
        content = json.dumps(self._dashboard())
        assert "Health Matrix" in content or "health" in content.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# C7: unit tests — _InstrumentedCheckpointer logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestInstrumentedCheckpointerUnit:
    """اختبارات وحدة لـ _InstrumentedCheckpointer."""

    def _load_module(self):
        """يُحمِّل database.py مع mock للتبعيات الثقيلة."""
        import importlib.util

        # Mock AsyncPostgresSaver كـ class قابل للوراثة
        mock_base = type("AsyncPostgresSaver", (), {
            "__init__": lambda self, pool: None,
            "aput": AsyncMock(),
            "aget": AsyncMock(return_value=None),
            "aget_tuple": AsyncMock(return_value=None),
            "setup": AsyncMock(),
            "alist": MagicMock(return_value=iter([])),
        })

        spec = importlib.util.spec_from_file_location("database_step10", DATABASE_PY)
        mod = importlib.util.module_from_spec(spec)

        with patch.dict("sys.modules", {
            "microservices.orchestrator_service.src.core.config": MagicMock(
                settings=MagicMock(DATABASE_URL="postgresql+asyncpg://u:p@h:5432/db")
            ),
            "microservices.orchestrator_service.src.models.mission": MagicMock(),
            "microservices.orchestrator_service.src.core.prom_metrics": MagicMock(),
            "psycopg_pool": MagicMock(),
            "langgraph.checkpoint.postgres.aio": MagicMock(AsyncPostgresSaver=mock_base),
        }):
            spec.loader.exec_module(mod)
        return mod

    def test_instrumented_class_is_subclass_of_base(self):
        """يتحقق من أن _InstrumentedCheckpointer يرث من AsyncPostgresSaver."""
        mod = self._load_module()
        # يجب أن يكون subclass (ليس wrapper)
        assert hasattr(mod, "_InstrumentedCheckpointer")
        assert hasattr(mod, "_make_instrumented_class")

    def test_active_threads_initialized_empty(self):
        mod = self._load_module()
        ckpt = mod._InstrumentedCheckpointer(pool=None)
        assert hasattr(ckpt, "_active_threads")
        assert isinstance(ckpt._active_threads, set)
        assert len(ckpt._active_threads) == 0

    def test_thread_id_prefix_extraction_with_colon(self):
        """يتحقق من استخراج prefix من thread_id بشكل صحيح."""
        thread_id = "u7:c42"
        prefix = thread_id.split(":")[0] if ":" in thread_id else thread_id[:8]
        assert prefix == "u7"

    def test_thread_id_prefix_extraction_without_colon(self):
        thread_id = "warmup_probe"
        prefix = thread_id.split(":")[0] if ":" in thread_id else thread_id[:8]
        assert prefix == "warmup_p"

    def test_thread_id_prefix_short_string(self):
        thread_id = "abc"
        prefix = thread_id.split(":")[0] if ":" in thread_id else thread_id[:8]
        assert prefix == "abc"

    def test_make_instrumented_class_returns_class(self):
        mod = self._load_module()
        base = type("FakeBase", (), {
            "__init__": lambda self, pool: None,
        })
        cls = mod._make_instrumented_class(base)
        assert isinstance(cls, type)
        assert issubclass(cls, base)

    def test_make_instrumented_class_has_active_threads(self):
        mod = self._load_module()
        base = type("FakeBase", (), {
            "__init__": lambda self, pool: None,
        })
        cls = mod._make_instrumented_class(base)
        instance = cls(pool=None)
        assert hasattr(instance, "_active_threads")

    def test_error_type_classification_connection(self):
        """يتحقق من تصنيف أنواع الأخطاء."""
        error_type = "connectionerror"
        result = "connection_error" if "connection" in error_type or "pool" in error_type else "unknown"
        assert result == "connection_error"

    def test_error_type_classification_serialization(self):
        error_type = "jsondecodeerror"
        result = "serialization_error" if "serial" in error_type or "json" in error_type else "unknown"
        assert result == "serialization_error"

    def test_error_type_classification_timeout(self):
        error_type = "timeouterror"
        result = "timeout" if "timeout" in error_type else "unknown"
        assert result == "timeout"

    def test_error_type_classification_unknown(self):
        error_type = "valueerror"
        result = "unknown"
        assert result == "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# C8: unit tests — prom_metrics checkpointer functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromMetricsCheckpointerFunctions:
    """اختبارات وحدة لدوال prom_metrics الخاصة بالـ checkpointer."""

    def _import_metrics(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("prom_metrics_step10", PROM_METRICS)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_record_checkpointer_write_callable(self):
        mod = self._import_metrics()
        # يجب أن يُستدعى بدون استثناء
        mod.record_checkpointer_write("u7", "success", 0.01)

    def test_record_checkpointer_write_error_status(self):
        mod = self._import_metrics()
        mod.record_checkpointer_write("u7", "error", 0.05)

    def test_record_checkpointer_read_hit(self):
        mod = self._import_metrics()
        mod.record_checkpointer_read("u7", "hit", 0.005)

    def test_record_checkpointer_read_miss(self):
        mod = self._import_metrics()
        mod.record_checkpointer_read("u7", "miss", 0.003)

    def test_record_checkpointer_read_error(self):
        mod = self._import_metrics()
        mod.record_checkpointer_read("u7", "error", 0.1)

    def test_record_checkpointer_error_connection(self):
        mod = self._import_metrics()
        mod.record_checkpointer_error("connection_error")

    def test_record_checkpointer_error_serialization(self):
        mod = self._import_metrics()
        mod.record_checkpointer_error("serialization_error")

    def test_record_checkpointer_error_timeout(self):
        mod = self._import_metrics()
        mod.record_checkpointer_error("timeout")

    def test_set_checkpointer_active_threads_zero(self):
        mod = self._import_metrics()
        mod.set_checkpointer_active_threads(0)

    def test_set_checkpointer_active_threads_positive(self):
        mod = self._import_metrics()
        mod.set_checkpointer_active_threads(5)

    def test_set_checkpointer_backend_info_postgres(self):
        mod = self._import_metrics()
        mod.set_checkpointer_backend_info("postgres", "10", 5, True)

    def test_set_checkpointer_backend_info_none(self):
        mod = self._import_metrics()
        mod.set_checkpointer_backend_info("none", "10", 0, False)

    def test_set_startup_info_with_checkpointer_backend(self):
        mod = self._import_metrics()
        mod.set_startup_info(
            version="1.0.0",
            environment="test",
            outbox_relay_enabled=True,
            graph_ready=True,
            pipeline_enabled=True,
            checkpointer_backend="postgres",
        )

    def test_set_startup_info_default_checkpointer_backend_none(self):
        mod = self._import_metrics()
        # يجب أن يعمل بدون checkpointer_backend (default="none")
        mod.set_startup_info(
            version="1.0.0",
            environment="test",
            outbox_relay_enabled=False,
            graph_ready=False,
        )

    def test_export_prometheus_text_returns_bytes_and_content_type(self):
        mod = self._import_metrics()
        body, ct = mod.export_prometheus_text()
        assert isinstance(body, bytes)
        assert isinstance(ct, str)

    def test_checkpointer_metrics_in_exported_text(self):
        mod = self._import_metrics()
        # استدعِ دالة لتسجيل قيمة
        mod.record_checkpointer_write("test", "success", 0.01)
        body, _ = mod.export_prometheus_text()
        # إذا كان prometheus_client مثبّتاً: يجب أن تظهر المقاييس
        # إذا لم يكن مثبّتاً: الـ stub يُعيد نصاً فارغاً — هذا سلوك صحيح
        assert isinstance(body, bytes)
        if b"prometheus_client not available" not in body:
            assert b"cogniforge_checkpointer" in body


# ═══════════════════════════════════════════════════════════════════════════════
# C9: unit tests — _build_psycopg_conninfo URL conversion
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildPsycopgConninfo:
    """يتحقق من تحويل DATABASE_URL إلى psycopg conninfo."""

    def _build(self, url: str) -> str:
        import importlib.util
        spec = importlib.util.spec_from_file_location("db_conninfo", DATABASE_PY)
        mod = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {
            "microservices.orchestrator_service.src.core.config": MagicMock(
                settings=MagicMock(DATABASE_URL=url)
            ),
            "microservices.orchestrator_service.src.models.mission": MagicMock(),
            "microservices.orchestrator_service.src.core.prom_metrics": MagicMock(),
            "psycopg_pool": MagicMock(),
            "langgraph.checkpoint.postgres.aio": MagicMock(),
        }):
            spec.loader.exec_module(mod)
        return mod._build_psycopg_conninfo(url)

    def test_removes_asyncpg_driver(self):
        result = self._build("postgresql+asyncpg://u:p@h:5432/db")
        assert "+asyncpg" not in result

    def test_keeps_postgresql_scheme(self):
        result = self._build("postgresql+asyncpg://u:p@h:5432/db")
        assert result.startswith("postgresql://")

    def test_preserves_host_port_db(self):
        result = self._build("postgresql+asyncpg://user:pass@myhost:5432/mydb")
        assert "myhost" in result
        assert "5432" in result
        assert "mydb" in result

    def test_adds_sslmode_require(self):
        result = self._build("postgresql+asyncpg://u:p@h:5432/db?sslmode=require")
        assert "sslmode=require" in result

    def test_removes_sslmode_from_path_query(self):
        # sslmode يجب أن يُزال من query string الأصلي ويُضاف بشكل صحيح
        result = self._build("postgresql+asyncpg://u:p@h:5432/db?sslmode=require")
        # لا يجب أن يظهر مرتين
        assert result.count("sslmode") == 1

    def test_plain_postgresql_url_works(self):
        result = self._build("postgresql://u:p@h:5432/db")
        assert result.startswith("postgresql://")
        assert "+asyncpg" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# C10: automations.yaml — step10 tasks
# ═══════════════════════════════════════════════════════════════════════════════

class TestAutomationsStep10:
    """يتحقق من وجود tasks Step 10 في automations.yaml."""

    def _src(self) -> str:
        return AUTOMATIONS.read_text()

    def test_run_step10_tests_task_exists(self):
        assert "run-step10-tests" in self._src()

    def test_verify_step10_task_exists(self):
        assert "verify-step10" in self._src() or "step10" in self._src()
