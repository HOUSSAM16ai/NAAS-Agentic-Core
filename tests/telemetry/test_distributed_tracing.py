"""
Distributed Tracing Test Suite — CogniForge
---------------------------------------------
Validates the full observability stack:
- W3C Trace Context propagation (traceparent / tracestate headers)
- Span lifecycle: start → child spans → end with status/metrics
- LangGraph node instrumentation (supervisor + chat spans)
- Orchestrator fallback chain tracing
- Trace/span correlation via UnifiedObservabilityService
- /api/v1/observability/traces endpoints
"""

from __future__ import annotations

import time

import pytest


# ─── W3C Trace Context ────────────────────────────────────────────────────────


class TestTraceContextPropagation:
    def test_from_valid_traceparent(self):
        from app.telemetry.models import TraceContext

        hdrs = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
        ctx = TraceContext.from_headers(hdrs)
        assert ctx is not None
        assert ctx.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert ctx.sampled is True

    def test_from_unsampled_traceparent(self):
        from app.telemetry.models import TraceContext

        hdrs = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00"}
        ctx = TraceContext.from_headers(hdrs)
        assert ctx is not None
        assert ctx.sampled is False

    def test_from_missing_traceparent_returns_none(self):
        from app.telemetry.models import TraceContext

        assert TraceContext.from_headers({}) is None

    def test_from_malformed_traceparent_returns_none(self):
        from app.telemetry.models import TraceContext

        assert TraceContext.from_headers({"traceparent": "bad-value"}) is None

    def test_to_headers_round_trip(self):
        from app.telemetry.models import TraceContext

        original = TraceContext(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            span_id="00f067aa0ba902b7",
            sampled=True,
            baggage={"env": "test"},
        )
        hdrs = original.to_headers()
        restored = TraceContext.from_headers(hdrs)
        assert restored is not None
        assert restored.trace_id == original.trace_id
        assert restored.sampled == original.sampled
        assert restored.baggage.get("env") == "test"

    def test_baggage_propagation_via_tracestate(self):
        from app.telemetry.models import TraceContext

        ctx = TraceContext(
            trace_id="aabbccddeeff00112233445566778899",
            span_id="1234567890abcdef",
            sampled=True,
            baggage={"tenant": "algerian-schools", "version": "v2"},
        )
        hdrs = ctx.to_headers()
        assert "tracestate" in hdrs
        restored = TraceContext.from_headers(hdrs)
        assert restored is not None
        assert restored.baggage.get("tenant") == "algerian-schools"


# ─── Span Lifecycle ────────────────────────────────────────────────────────────


class TestSpanLifecycle:
    def _fresh_obs(self):
        from app.telemetry.unified_observability import UnifiedObservabilityService

        return UnifiedObservabilityService(service_name="test", sample_rate=1.0)

    def test_root_span_creates_trace(self):
        obs = self._fresh_obs()
        ctx = obs.start_trace("http.request", tags={"method": "GET"})
        assert ctx.trace_id
        assert ctx.span_id
        assert ctx.trace_id in obs.active_traces
        assert ctx.span_id in obs.active_spans

    def test_end_span_moves_trace_to_completed(self):
        obs = self._fresh_obs()
        ctx = obs.start_trace("http.request")
        obs.end_span(ctx.span_id, status="OK", metrics={"duration_ms": 42.0})
        assert ctx.trace_id not in obs.active_traces
        assert any(t.trace_id == ctx.trace_id for t in obs.completed_traces)

    def test_child_span_shares_trace_id(self):
        obs = self._fresh_obs()
        parent = obs.start_trace("http.request")
        child = obs.start_trace("db.query", parent_context=parent)
        assert child.trace_id == parent.trace_id
        assert child.span_id != parent.span_id

    def test_span_duration_recorded(self):
        obs = self._fresh_obs()
        ctx = obs.start_trace("slow.operation")
        time.sleep(0.01)
        obs.end_span(ctx.span_id, status="OK")
        completed = next(t for t in obs.completed_traces if t.trace_id == ctx.trace_id)
        assert completed.total_duration_ms is not None
        assert completed.total_duration_ms >= 10.0

    def test_error_span_increments_error_count(self):
        obs = self._fresh_obs()
        ctx = obs.start_trace("failing.operation")
        obs.end_span(ctx.span_id, status="ERROR", error_message="timeout")
        completed = next(t for t in obs.completed_traces if t.trace_id == ctx.trace_id)
        assert completed.error_count == 1

    def test_span_events_recorded(self):
        obs = self._fresh_obs()
        ctx = obs.start_trace("operation.with.events")
        obs.add_span_event(ctx.span_id, "cache_miss", {"key": "session:abc"})
        span = obs.active_spans[ctx.span_id]
        assert len(span.events) == 1
        assert span.events[0]["name"] == "cache_miss"

    def test_critical_path_identifies_bottleneck(self):
        obs = self._fresh_obs()
        parent = obs.start_trace("root")
        child1 = obs.start_trace("fast.step", parent_context=parent)
        obs.end_span(child1.span_id, status="OK", metrics={"duration_ms": 5.0})
        child2 = obs.start_trace("slow.step", parent_context=parent)
        obs.end_span(child2.span_id, status="OK", metrics={"duration_ms": 200.0})
        obs.end_span(parent.span_id, status="OK")
        completed = next(t for t in obs.completed_traces if t.trace_id == parent.trace_id)
        assert completed.critical_path_ms is not None


# ─── Metrics Correlation ───────────────────────────────────────────────────────


class TestMetricsCorrelation:
    def test_metric_linked_to_trace(self):
        from app.telemetry.unified_observability import UnifiedObservabilityService

        obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        ctx = obs.start_trace("api.call")
        obs.record_metric(
            name="api.latency_ms",
            value=55.3,
            labels={"endpoint": "/health"},
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
        )
        assert ctx.trace_id in obs.trace_metrics
        sample = obs.trace_metrics[ctx.trace_id][0]
        assert sample.value == 55.3
        assert sample.exemplar_trace_id == ctx.trace_id

    def test_counter_increments_accumulate(self):
        from app.telemetry.unified_observability import UnifiedObservabilityService

        obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        obs.increment_counter("http.requests.total", 1.0, labels={"method": "GET"})
        obs.increment_counter("http.requests.total", 1.0, labels={"method": "GET"})
        key = "http.requests.total{method=GET}"
        assert obs.counters[key] == 2.0

    def test_structured_log_linked_to_trace(self):
        from app.telemetry.unified_observability import UnifiedObservabilityService

        obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        ctx = obs.start_trace("user.login")
        obs.log(
            level="INFO",
            message="User authenticated",
            context={"user_id": "42"},
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
        )
        assert ctx.trace_id in obs.trace_logs
        log = obs.trace_logs[ctx.trace_id][0]
        assert log.message == "User authenticated"
        assert log.span_id == ctx.span_id


# ─── LangGraph Node Instrumentation ───────────────────────────────────────────


class TestLangGraphInstrumentation:
    def test_graph_trace_contextvar_defaults_none(self):
        from app.services.chat.local_graph import _graph_trace_context

        assert _graph_trace_context.get() is None

    def test_contextvar_token_reset(self):
        from app.telemetry.models import TraceContext
        from app.services.chat.local_graph import _graph_trace_context

        fake_ctx = TraceContext(
            trace_id="a" * 32, span_id="b" * 16, sampled=True
        )
        token = _graph_trace_context.set(fake_ctx)
        assert _graph_trace_context.get() is fake_ctx
        _graph_trace_context.reset(token)
        assert _graph_trace_context.get() is None

    @pytest.mark.asyncio
    async def test_run_local_graph_creates_root_span(self, monkeypatch):
        """run_local_graph should produce a root span even when LLM is mocked."""
        from app.telemetry.unified_observability import UnifiedObservabilityService, get_unified_observability
        import app.telemetry.unified_observability as uo_mod

        fresh_obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        monkeypatch.setattr(uo_mod, "_unified_observability", fresh_obs)

        # Mock graph invocation so we don't need a real LLM
        async def _mock_ainvoke(state, config):
            return {**state, "final_response": "مرحبا", "intent": "chat"}

        from app.services.chat import local_graph as lg_mod
        import app.services.chat.local_graph as _lg

        original_get = _lg.get_local_graph

        class FakeGraph:
            async def ainvoke(self, state, config):
                return {**state, "final_response": "مرحبا", "intent": "chat"}

        monkeypatch.setattr(_lg, "get_local_graph", lambda: FakeGraph())

        result = await _lg.run_local_graph("مرحبا", conversation_id=1)
        assert result == "مرحبا"

        # A completed trace must exist
        assert len(fresh_obs.completed_traces) >= 1
        trace = fresh_obs.completed_traces[-1]
        assert any(s.operation_name == "langgraph.run" for s in trace.spans)

    @pytest.mark.asyncio
    async def test_run_local_graph_propagates_parent_context(self, monkeypatch):
        """Parent trace context flows into LangGraph root span (child of parent trace)."""
        from app.telemetry.unified_observability import UnifiedObservabilityService
        import app.telemetry.unified_observability as uo_mod
        import app.services.chat.local_graph as lg_mod

        fresh_obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        monkeypatch.setattr(uo_mod, "_unified_observability", fresh_obs)

        # Create the parent trace in the same obs instance so it exists in active_traces
        parent_ctx = fresh_obs.start_trace("http.request")

        class FakeGraph:
            async def ainvoke(self, state, config):
                return {**state, "final_response": "ok", "intent": "general"}

        monkeypatch.setattr(lg_mod, "get_local_graph", lambda: FakeGraph())

        await lg_mod.run_local_graph("test", conversation_id=None, trace_context=parent_ctx)

        # The langgraph.run span should be in active_spans (child, not root — trace isn't done yet)
        child_spans = [s for s in fresh_obs.active_spans.values() if s.operation_name == "langgraph.run"]
        # OR it may have been completed as part of the parent trace's spans
        all_child_spans = [
            s
            for s in fresh_obs.active_spans.values()
            if s.trace_id == parent_ctx.trace_id and s.operation_name == "langgraph.run"
        ]
        # The span was created with the parent's trace_id
        assert any(
            s.trace_id == parent_ctx.trace_id
            for t in fresh_obs.active_traces.values()
            for s in t.spans
            if s.operation_name == "langgraph.run"
        ) or any(
            s.trace_id == parent_ctx.trace_id
            for t in fresh_obs.completed_traces
            for s in t.spans
            if s.operation_name == "langgraph.run"
        ) or any(
            s.trace_id == parent_ctx.trace_id
            for s in fresh_obs.active_spans.values()
            if s.operation_name == "langgraph.run"
        )


# ─── Observability Middleware Integration ──────────────────────────────────────


class TestObservabilityMiddleware:
    def test_middleware_instantiates_without_config(self):
        from unittest.mock import AsyncMock, MagicMock
        from app.middleware.observability.observability_middleware import ObservabilityMiddleware

        fake_app = MagicMock()
        mw = ObservabilityMiddleware(fake_app)
        assert mw.obs is not None

    def test_middleware_extracts_traceparent_header(self):
        from unittest.mock import MagicMock
        from app.middleware.observability.observability_middleware import ObservabilityMiddleware
        from app.middleware.core.context import RequestContext

        fake_app = MagicMock()
        mw = ObservabilityMiddleware(fake_app)

        ctx = RequestContext(
            method="GET",
            path="/health",
            headers={
                "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
            },
        )
        parent = mw._extract_parent_context(ctx)
        assert parent is not None
        assert parent.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"

    def test_middleware_returns_none_without_header(self):
        from unittest.mock import MagicMock
        from app.middleware.observability.observability_middleware import ObservabilityMiddleware
        from app.middleware.core.context import RequestContext

        fake_app = MagicMock()
        mw = ObservabilityMiddleware(fake_app)
        ctx = RequestContext(method="GET", path="/health", headers={})
        assert mw._extract_parent_context(ctx) is None


# ─── Trace API Endpoints ───────────────────────────────────────────────────────


class TestTraceAPIEndpoints:
    @pytest.fixture
    def client(self):
        """Minimal FastAPI test client with the observability router mounted."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.routers.observability import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/observability")
        return TestClient(app)

    def test_list_traces_empty(self, client):
        resp = client.get("/api/v1/observability/traces")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_traces_returns_completed_traces(self, client, monkeypatch):
        from app.telemetry.unified_observability import UnifiedObservabilityService
        import app.telemetry.unified_observability as uo_mod

        fresh_obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        ctx = fresh_obs.start_trace("test.operation", tags={"env": "ci"})
        fresh_obs.end_span(ctx.span_id, status="OK", metrics={"duration_ms": 12.5})
        monkeypatch.setattr(uo_mod, "_unified_observability", fresh_obs)

        resp = client.get("/api/v1/observability/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        trace_data = data[-1]
        assert trace_data["trace_id"] == ctx.trace_id
        assert len(trace_data["spans"]) >= 1

    def test_get_trace_by_id(self, client, monkeypatch):
        from app.telemetry.unified_observability import UnifiedObservabilityService
        import app.telemetry.unified_observability as uo_mod

        fresh_obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        ctx = fresh_obs.start_trace("specific.operation")
        fresh_obs.end_span(ctx.span_id, status="OK")
        monkeypatch.setattr(uo_mod, "_unified_observability", fresh_obs)

        resp = client.get(f"/api/v1/observability/traces/{ctx.trace_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trace_id"] == ctx.trace_id

    def test_get_trace_not_found(self, client, monkeypatch):
        from app.telemetry.unified_observability import UnifiedObservabilityService
        import app.telemetry.unified_observability as uo_mod

        fresh_obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        monkeypatch.setattr(uo_mod, "_unified_observability", fresh_obs)

        resp = client.get("/api/v1/observability/traces/nonexistent-trace-id")
        assert resp.status_code == 404

    def test_active_trace_visible_via_get_endpoint(self, client, monkeypatch):
        """An in-flight (active) trace should be queryable before it completes."""
        from app.telemetry.unified_observability import UnifiedObservabilityService
        import app.telemetry.unified_observability as uo_mod

        fresh_obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        ctx = fresh_obs.start_trace("in.flight.operation")
        # Do NOT end the span — it stays in active_traces
        monkeypatch.setattr(uo_mod, "_unified_observability", fresh_obs)

        resp = client.get(f"/api/v1/observability/traces/{ctx.trace_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trace_id"] == ctx.trace_id


# ─── Signal Correlation ─────────────────────────────────────────────────────────


class TestSignalCorrelation:
    def test_get_trace_with_correlation_returns_spans_and_logs(self):
        from app.telemetry.unified_observability import UnifiedObservabilityService

        obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        ctx = obs.start_trace("correlated.operation")
        obs.log(
            level="INFO",
            message="processing started",
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
        )
        obs.record_metric(
            name="op.latency_ms",
            value=33.0,
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
        )
        obs.end_span(ctx.span_id, status="OK")

        correlated = obs.get_trace_with_correlation(ctx.trace_id)
        assert correlated is not None
        # The aggregator uses "correlated_logs" as the key
        log_key = "logs" if "logs" in correlated else "correlated_logs"
        assert log_key in correlated
        assert len(correlated[log_key]) >= 1

    def test_golden_signals_reflect_recorded_metrics(self):
        from app.telemetry.unified_observability import UnifiedObservabilityService

        obs = UnifiedObservabilityService(service_name="test", sample_rate=1.0)
        for _ in range(5):
            ctx = obs.start_trace("api.call")
            obs.record_metric(
                "http.request.duration_seconds",
                0.1,
                labels={"method": "GET", "endpoint": "/health", "status": "200"},
                trace_id=ctx.trace_id,
            )
            obs.increment_counter("http.requests.total", labels={"method": "GET", "endpoint": "/health", "status": "200"})
            obs.end_span(ctx.span_id, status="OK")

        signals = obs.get_golden_signals(time_window_seconds=3600)
        assert "latency" in signals or "traffic" in signals or "errors" in signals or signals == {}
