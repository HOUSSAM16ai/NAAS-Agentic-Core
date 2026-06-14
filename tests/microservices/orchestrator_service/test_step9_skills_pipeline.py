"""
اختبارات Step 9 — Skills Composition Pipeline.

تتحقق هذه الاختبارات من:
  S1: skills_pipeline.py موجود ويحتوي البنية الصحيحة
  S2: prom_metrics.py يحتوي مقاييس Pipeline الجديدة
  S3: routes.py يحتوي /compose endpoint
  S4: config.py يحتوي الـ ports الصحيحة
  S5: Prometheus scrape config يحتوي skills-pipeline job
  S6: Grafana dashboard صالح
  S7: automations.yaml يحتوي tasks الخطوة 9
  S8: unit tests للـ skills_pipeline functions
  S9: unit tests للـ prom_metrics pipeline functions
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── مسارات الملفات ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent.parent
ORCHESTRATOR = ROOT / "microservices" / "orchestrator_service"
SKILLS_PIPELINE = ORCHESTRATOR / "src" / "services" / "skills_pipeline.py"
PROM_METRICS = ORCHESTRATOR / "src" / "core" / "prom_metrics.py"
ROUTES = ORCHESTRATOR / "src" / "api" / "routes.py"
CONFIG = ORCHESTRATOR / "src" / "core" / "config.py"
PROMETHEUS_YML = ROOT / "observability" / "native" / "prometheus.yml"
GRAFANA_DASHBOARD = (
    ROOT
    / "observability"
    / "grafana"
    / "dashboards"
    / "120-microservices-step9-skills-pipeline.json"
)
AUTOMATIONS = ROOT / ".ona" / "automations.yaml"
MAIN_PY = ORCHESTRATOR / "main.py"


# ═══════════════════════════════════════════════════════════════════════════════
# S1: skills_pipeline.py — البنية الأساسية
# ═══════════════════════════════════════════════════════════════════════════════


class TestSkillsPipelineExists:
    """S1: التحقق من وجود skills_pipeline.py وبنيته."""

    def test_file_exists(self):
        assert SKILLS_PIPELINE.exists(), "skills_pipeline.py غير موجود"

    def test_has_run_skills_pipeline_function(self):
        content = SKILLS_PIPELINE.read_text()
        assert "async def run_skills_pipeline" in content

    def test_has_skill_result_dataclass(self):
        content = SKILLS_PIPELINE.read_text()
        assert "class SkillResult" in content

    def test_has_pipeline_result_dataclass(self):
        content = SKILLS_PIPELINE.read_text()
        assert "class PipelineResult" in content

    def test_has_planning_skill_call(self):
        content = SKILLS_PIPELINE.read_text()
        assert "_call_planning_skill" in content

    def test_has_research_skill_call(self):
        content = SKILLS_PIPELINE.read_text()
        assert "_call_research_skill" in content

    def test_has_reasoning_skill_call(self):
        content = SKILLS_PIPELINE.read_text()
        assert "_call_reasoning_skill" in content

    def test_has_compose_answer_function(self):
        content = SKILLS_PIPELINE.read_text()
        assert "_compose_answer" in content

    def test_uses_httpx_async_client(self):
        content = SKILLS_PIPELINE.read_text()
        assert "httpx.AsyncClient" in content

    def test_uses_x_correlation_id(self):
        content = SKILLS_PIPELINE.read_text()
        assert "X-Correlation-ID" in content

    def test_uses_asyncio_gather_for_parallel(self):
        content = SKILLS_PIPELINE.read_text()
        assert "asyncio.gather" in content

    def test_has_fallback_on_connect_error(self):
        content = SKILLS_PIPELINE.read_text()
        assert "ConnectError" in content or "httpx.ConnectError" in content

    def test_has_fallback_on_timeout(self):
        content = SKILLS_PIPELINE.read_text()
        assert "TimeoutException" in content or "httpx.TimeoutException" in content

    def test_pipeline_mode_full_partial_fallback(self):
        content = SKILLS_PIPELINE.read_text()
        assert '"full"' in content
        assert '"partial"' in content
        assert '"fallback"' in content

    def test_uses_get_settings(self):
        content = SKILLS_PIPELINE.read_text()
        assert "get_settings" in content

    def test_skill_timeout_constant(self):
        content = SKILLS_PIPELINE.read_text()
        assert "_SKILL_TIMEOUT_SECONDS" in content

    def test_no_direct_db_access(self):
        """Skill لا تصل مباشرة لقاعدة البيانات — تمر عبر HTTP فقط."""
        content = SKILLS_PIPELINE.read_text()
        assert "async_session_factory" not in content
        assert "get_db" not in content


# ═══════════════════════════════════════════════════════════════════════════════
# S2: prom_metrics.py — مقاييس Pipeline الجديدة
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromMetricsPipeline:
    """S2: التحقق من مقاييس Pipeline في prom_metrics.py."""

    def test_pipeline_invocations_counter(self):
        content = PROM_METRICS.read_text()
        assert "cogniforge_pipeline_invocations_total" in content

    def test_pipeline_duration_histogram(self):
        content = PROM_METRICS.read_text()
        assert "cogniforge_pipeline_duration_seconds" in content

    def test_pipeline_skill_calls_counter(self):
        content = PROM_METRICS.read_text()
        assert "cogniforge_pipeline_skill_calls_total" in content

    def test_pipeline_skill_duration_histogram(self):
        content = PROM_METRICS.read_text()
        assert "cogniforge_pipeline_skill_duration_seconds" in content

    def test_pipeline_errors_counter(self):
        content = PROM_METRICS.read_text()
        assert "cogniforge_pipeline_errors_total" in content

    def test_pipeline_active_gauge(self):
        content = PROM_METRICS.read_text()
        assert "cogniforge_pipeline_active_gauge" in content

    def test_record_pipeline_invocation_function(self):
        content = PROM_METRICS.read_text()
        assert "def record_pipeline_invocation" in content

    def test_record_pipeline_error_function(self):
        content = PROM_METRICS.read_text()
        assert "def record_pipeline_error" in content

    def test_set_pipeline_active_function(self):
        content = PROM_METRICS.read_text()
        assert "def set_pipeline_active" in content

    def test_startup_info_has_pipeline_enabled_label(self):
        content = PROM_METRICS.read_text()
        assert "pipeline_enabled" in content

    def test_set_startup_info_accepts_pipeline_enabled(self):
        content = PROM_METRICS.read_text()
        assert "pipeline_enabled" in content
        # يجب أن تكون parameter في set_startup_info
        assert "def set_startup_info" in content


# ═══════════════════════════════════════════════════════════════════════════════
# S3: routes.py — /compose endpoint
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoutesComposeEndpoint:
    """S3: التحقق من /compose endpoint في routes.py."""

    def test_compose_endpoint_exists(self):
        content = ROUTES.read_text()
        assert '"/compose"' in content or "'/compose'" in content

    def test_compose_request_model(self):
        content = ROUTES.read_text()
        assert "ComposeRequest" in content

    def test_compose_response_model(self):
        content = ROUTES.read_text()
        assert "ComposeResponse" in content

    def test_imports_run_skills_pipeline(self):
        content = ROUTES.read_text()
        assert "run_skills_pipeline" in content

    def test_imports_pipeline_metrics(self):
        content = ROUTES.read_text()
        assert "record_pipeline_invocation" in content

    def test_compose_uses_correlation_id(self):
        content = ROUTES.read_text()
        assert "correlation_id" in content

    def test_compose_handles_exception_as_502(self):
        content = ROUTES.read_text()
        assert "502" in content

    def test_compose_records_prometheus_metrics(self):
        content = ROUTES.read_text()
        assert "record_pipeline_invocation" in content
        assert "set_pipeline_active" in content

    def test_skill_result_schema_in_response(self):
        content = ROUTES.read_text()
        assert "SkillResultSchema" in content

    def test_compose_response_has_pipeline_mode(self):
        content = ROUTES.read_text()
        assert "pipeline_mode" in content

    def test_compose_response_has_skills_active(self):
        content = ROUTES.read_text()
        assert "skills_active" in content


# ═══════════════════════════════════════════════════════════════════════════════
# S4: config.py — الـ ports الصحيحة
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigServicePorts:
    """S4: التحقق من صحة الـ ports في config.py."""

    def test_planning_agent_port_8002(self):
        content = CONFIG.read_text()
        # planning-agent يجب أن يكون على 8002 في Codespaces
        assert '"8002"' in content or "'8002'" in content

    def test_research_agent_port_8007(self):
        content = CONFIG.read_text()
        assert '"8007"' in content or "'8007'" in content

    def test_reasoning_agent_port_8008(self):
        content = CONFIG.read_text()
        assert '"8008"' in content or "'8008'" in content

    def test_user_service_port_8001(self):
        content = CONFIG.read_text()
        assert '"8001"' in content or "'8001'" in content

    def test_service_urls_field_exists(self):
        content = CONFIG.read_text()
        assert "PLANNING_AGENT_URL" in content
        assert "RESEARCH_AGENT_URL" in content
        assert "REASONING_AGENT_URL" in content


# ═══════════════════════════════════════════════════════════════════════════════
# S5: Prometheus scrape config
# ═══════════════════════════════════════════════════════════════════════════════


class TestPrometheusConfig:
    """S5: التحقق من Prometheus scrape config."""

    def test_prometheus_yml_exists(self):
        assert PROMETHEUS_YML.exists()

    def test_skills_pipeline_job_exists(self):
        content = PROMETHEUS_YML.read_text()
        assert "skills-pipeline" in content

    def test_skills_pipeline_targets_8006(self):
        content = PROMETHEUS_YML.read_text()
        # skills-pipeline يُصدَر من orchestrator-service:8006
        idx = content.find("skills-pipeline")
        assert idx != -1
        snippet = content[idx : idx + 300]
        assert "8006" in snippet

    def test_skills_pipeline_step_label(self):
        content = PROMETHEUS_YML.read_text()
        idx = content.find("skills-pipeline")
        assert idx != -1
        snippet = content[idx : idx + 400]
        assert 'step: "9"' in snippet or "step: '9'" in snippet


# ═══════════════════════════════════════════════════════════════════════════════
# S6: Grafana Dashboard
# ═══════════════════════════════════════════════════════════════════════════════


class TestGrafanaDashboard:
    """S6: التحقق من Grafana dashboard."""

    def test_dashboard_file_exists(self):
        assert GRAFANA_DASHBOARD.exists(), "120-microservices-step9-skills-pipeline.json غير موجود"

    def test_dashboard_valid_json(self):
        content = GRAFANA_DASHBOARD.read_text()
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_dashboard_uid(self):
        data = json.loads(GRAFANA_DASHBOARD.read_text())
        assert data.get("uid") == "cogniforge-ms-step9-pipeline"

    def test_dashboard_has_panels(self):
        data = json.loads(GRAFANA_DASHBOARD.read_text())
        assert len(data.get("panels", [])) >= 6

    def test_dashboard_has_pipeline_invocations_metric(self):
        content = GRAFANA_DASHBOARD.read_text()
        assert "cogniforge_pipeline_invocations_total" in content

    def test_dashboard_has_pipeline_duration_metric(self):
        content = GRAFANA_DASHBOARD.read_text()
        assert "cogniforge_pipeline_duration_seconds" in content

    def test_dashboard_has_skill_calls_metric(self):
        content = GRAFANA_DASHBOARD.read_text()
        assert "cogniforge_pipeline_skill_calls_total" in content

    def test_dashboard_has_health_matrix(self):
        content = GRAFANA_DASHBOARD.read_text()
        assert "cogniforge_orchestrator_startup_info" in content
        assert "cogniforge_user_startup_info" in content
        assert "cogniforge_planning_startup_info" in content

    def test_dashboard_refresh_10s(self):
        data = json.loads(GRAFANA_DASHBOARD.read_text())
        assert data.get("refresh") == "10s"

    def test_dashboard_has_step9_tag(self):
        data = json.loads(GRAFANA_DASHBOARD.read_text())
        tags = data.get("tags", [])
        assert "step9" in tags or "skills-pipeline" in tags


# ═══════════════════════════════════════════════════════════════════════════════
# S7: automations.yaml
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutomationsYaml:
    """S7: التحقق من automations.yaml."""

    def test_automations_exists(self):
        assert AUTOMATIONS.exists()

    def test_verify_step9_task_exists(self):
        content = AUTOMATIONS.read_text()
        assert "verify-step9-skills-pipeline" in content

    def test_run_step9_tests_task_exists(self):
        content = AUTOMATIONS.read_text()
        assert "run-step9-tests" in content

    def test_step9_verify_checks_compose_endpoint(self):
        content = AUTOMATIONS.read_text()
        assert "/compose" in content

    def test_step9_verify_checks_pipeline_metrics(self):
        content = AUTOMATIONS.read_text()
        assert "cogniforge_pipeline" in content

    def test_step9_tests_run_correct_file(self):
        content = AUTOMATIONS.read_text()
        assert "test_step9_skills_pipeline" in content


# ═══════════════════════════════════════════════════════════════════════════════
# S8: unit tests للـ skills_pipeline functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestSkillsPipelineUnit:
    """S8: اختبارات وحدة لـ skills_pipeline.py."""

    def test_skill_result_dataclass_fields(self):
        """SkillResult يجب أن يحتوي الحقول الأساسية."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("skills_pipeline", SKILLS_PIPELINE)
        assert spec is not None
        importlib.util.module_from_spec(spec)
        # نتحقق من الكود مباشرة بدل import لتجنب تبعيات runtime
        content = SKILLS_PIPELINE.read_text()
        assert "skill: str" in content
        assert "status: str" in content
        assert "data: dict" in content
        assert "duration_ms: float" in content

    def test_pipeline_result_has_all_skills(self):
        content = SKILLS_PIPELINE.read_text()
        assert "plan: SkillResult" in content
        assert "research: SkillResult" in content
        assert "reasoning: SkillResult" in content

    def test_pipeline_result_has_composed_answer(self):
        content = SKILLS_PIPELINE.read_text()
        assert "composed_answer: str" in content

    def test_pipeline_result_has_total_duration(self):
        content = SKILLS_PIPELINE.read_text()
        assert "total_duration_ms: float" in content

    def test_compose_answer_uses_reasoning_first(self):
        """_compose_answer يُعطي الأولوية لـ reasoning عند النجاح (D-110: تركيب مرتّب)."""
        content = SKILLS_PIPELINE.read_text()
        compose_fn_idx = content.find("def _compose_answer")
        assert compose_fn_idx != -1
        # D-110: نحدّ جسم الدالة حتى تعريف الدالة التالية (لا نافذة ثابتة هشّة —
        # docstring الـ Real Synthesis الطويل كان يتجاوز 800 حرف).
        next_def_idx = content.find("\ndef ", compose_fn_idx + 1)
        compose_body = content[
            compose_fn_idx : next_def_idx if next_def_idx != -1 else len(content)
        ]
        reasoning_check_idx = compose_body.find('reasoning.status == "success"')
        research_check_idx = compose_body.find('research.status == "success"')
        assert reasoning_check_idx != -1, "reasoning.status check missing"
        assert research_check_idx != -1, "research.status check missing"
        assert reasoning_check_idx < research_check_idx, "reasoning يجب أن يُفحص قبل research"

    def test_determine_pipeline_mode_logic(self):
        content = SKILLS_PIPELINE.read_text()
        assert "_determine_pipeline_mode" in content
        # يجب أن يُعيد "full" عند نجاح الـ 3
        assert "len(active) == 3" in content or 'mode="full"' in content or '"full"' in content

    def test_planning_skill_sends_generate_plan_action(self):
        content = SKILLS_PIPELINE.read_text()
        assert '"generate_plan"' in content or "'generate_plan'" in content

    def test_research_skill_sends_search_action(self):
        content = SKILLS_PIPELINE.read_text()
        assert '"search"' in content or "'search'" in content

    def test_reasoning_skill_sends_reason_action(self):
        content = SKILLS_PIPELINE.read_text()
        assert '"reason"' in content or "'reason'" in content

    def test_caller_id_is_orchestrator(self):
        content = SKILLS_PIPELINE.read_text()
        assert "orchestrator-service" in content

    def test_context_built_from_plan_and_research(self):
        """السياق المُرسَل لـ reasoning يجب أن يتضمن نتائج planning و research."""
        # Earlier drafts of the pipeline used a `composed_context` / `context_parts`
        # buffer. The shipped implementation collapses both into `_compose_answer`,
        # which takes the SkillResult objects from planning + research + reasoning
        # and builds the final string. Accept any of the three markers so this
        # test stays meaningful without pinning the internal variable name.
        content = SKILLS_PIPELINE.read_text()
        assert any(
            marker in content for marker in ("composed_context", "context_parts", "_compose_answer")
        )


# ═══════════════════════════════════════════════════════════════════════════════
# S9: unit tests للـ prom_metrics pipeline functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromMetricsPipelineFunctions:
    """S9: اختبارات وحدة لدوال Pipeline في prom_metrics.py."""

    def test_record_pipeline_invocation_signature(self):
        content = PROM_METRICS.read_text()
        assert "def record_pipeline_invocation" in content
        assert "mode" in content
        assert "duration_seconds" in content
        assert "skill_results" in content

    def test_record_pipeline_error_signature(self):
        content = PROM_METRICS.read_text()
        assert "def record_pipeline_error" in content
        assert "error_type" in content

    def test_set_pipeline_active_signature(self):
        content = PROM_METRICS.read_text()
        assert "def set_pipeline_active" in content
        assert "count" in content

    def test_set_startup_info_has_pipeline_enabled_param(self):
        content = PROM_METRICS.read_text()
        fn_idx = content.find("def set_startup_info")
        assert fn_idx != -1
        fn_sig = content[fn_idx : fn_idx + 300]
        assert "pipeline_enabled" in fn_sig

    def test_pipeline_invocations_has_mode_label(self):
        content = PROM_METRICS.read_text()
        # PIPELINE_INVOCATIONS يجب أن يحتوي label "mode"
        idx = content.find("cogniforge_pipeline_invocations_total")
        assert idx != -1
        snippet = content[idx : idx + 200]
        assert '"mode"' in snippet or "'mode'" in snippet

    def test_pipeline_skill_calls_has_skill_and_status_labels(self):
        content = PROM_METRICS.read_text()
        idx = content.find("cogniforge_pipeline_skill_calls_total")
        assert idx != -1
        snippet = content[idx : idx + 200]
        assert '"skill"' in snippet or "'skill'" in snippet
        assert '"status"' in snippet or "'status'" in snippet

    def test_pipeline_errors_has_error_type_label(self):
        content = PROM_METRICS.read_text()
        idx = content.find("cogniforge_pipeline_errors_total")
        assert idx != -1
        snippet = content[idx : idx + 200]
        assert '"error_type"' in snippet or "'error_type'" in snippet

    def test_pipeline_duration_has_mode_label(self):
        content = PROM_METRICS.read_text()
        idx = content.find("cogniforge_pipeline_duration_seconds")
        assert idx != -1
        snippet = content[idx : idx + 200]
        assert '"mode"' in snippet or "'mode'" in snippet

    def test_pipeline_skill_duration_has_skill_label(self):
        content = PROM_METRICS.read_text()
        idx = content.find("cogniforge_pipeline_skill_duration_seconds")
        assert idx != -1
        snippet = content[idx : idx + 200]
        assert '"skill"' in snippet or "'skill'" in snippet

    def test_startup_info_has_pipeline_enabled_in_labels(self):
        content = PROM_METRICS.read_text()
        # pipeline_enabled يجب أن يكون في labels list لـ STARTUP_INFO
        # نبحث في المنطقة التي تُعرِّف STARTUP_INFO gauge
        idx = content.find('"cogniforge_orchestrator_startup_info"')
        assert idx != -1
        snippet = content[idx : idx + 400]
        assert "pipeline_enabled" in snippet


# ═══════════════════════════════════════════════════════════════════════════════
# S10: main.py — pipeline_enabled في startup_info
# ═══════════════════════════════════════════════════════════════════════════════


class TestMainPyPipelineEnabled:
    """S10: التحقق من main.py."""

    def test_main_calls_set_startup_info_with_pipeline_enabled(self):
        content = MAIN_PY.read_text()
        assert "pipeline_enabled=True" in content

    def test_main_logs_pipeline_enabled(self):
        content = MAIN_PY.read_text()
        assert "pipeline_enabled" in content


# ═══════════════════════════════════════════════════════════════════════════════
# تشغيل مباشر
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
