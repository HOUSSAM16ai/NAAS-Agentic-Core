"""
Path-aware observability for WebSocket chat turns.

This module is a thin, opt-in adapter on top of `UnifiedObservabilityService`
(`app/telemetry/unified_observability.py`) that gives the WS chat path a
top-level span + structured metrics without mutating any existing tracing
behavior.

Live consumers (proven by import + call chain):
    - `app/api/routers/customer_chat.py` (per-turn `ws_chat_turn` context)
    - `app/api/routers/admin.py`         (per-turn `ws_chat_turn` context)

Closes the WS slice of ISS-005 (HTTP middleware tracing did not cover WS frames).

Path types — taxonomy (single source of truth):
    educational    — supervisor classified the question as exam/subject content
    general_chat   — small-talk / general knowledge
    fallback       — orchestrator HTTP failed and a local engine produced the reply
    admin          — admin chat WS endpoint (regardless of intent)
    unknown        — turn ended before classification was possible

The observer NEVER raises out of the live path. Every operation that touches
the underlying `UnifiedObservabilityService` is wrapped — observability MUST
NOT break a real chat turn.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger("cogniforge.path_observer")

PathType = Literal["educational", "general_chat", "fallback", "admin", "unknown"]

_VALID_PATHS: frozenset[str] = frozenset(
    {"educational", "general_chat", "fallback", "admin", "unknown"}
)

# Same token families as `app/services/chat/local_graph.py:_classify_intent`.
# Duplicated intentionally so the router can classify before the graph runs
# (and without taking a hard dependency on local_graph's private API).
_EDUCATIONAL_PATTERNS = [
    r"(تمرين|مسألة|شرح|درس|مادة|كيفية حل|باكالوريا|بكالوريا|bac)",
    r"(فيزياء|رياضيات|كيمياء|تاريخ|جغرافيا|أدب|فلسفة|علوم|إحصاء|جبر)",
    r"(exercise|problem|solve|lesson|physics|math|chemistry|history|geography)",
    r"(حل|شرح لي|وضح لي|علمني|أريد أن أفهم|كيف أحل|ما هو الحل)",
]
# ISS-075 (D-063): regex مُحدَّث ليقبل امتدادات التحية الطبيعية
# (نسخة مطابقة من local_graph.py — D-013 يفرض تكرار التحديث).
_GREETING_PATTERNS = [
    r"^(?:و\s*)?(?:عليكم\s+)?السلام(?:\s+عليكم)?(?:\s+و?رحم[ةى]\s+الله)?(?:\s+و?بركاته)?[\s\W]*$",
    r"^(مرحبا|أهلاً?|أهلا|هلاً?|هلا)(?:\s+\S+){0,3}[\s\W]*$",
    r"^(hello|hi|hey|salam|بونجور|bonjour|salut|good\s+(morning|afternoon|evening))(?:\s+\S+){0,2}[\s\W]*$",
    r"^(كيف\s+حالك|ما\s+أخبارك|how\s+are\s+you|كيف\s+الأحوال)(?:\s+\S+){0,4}[\s\W]*$",
    r"^(شكرا|شكراً|merci|thank\s+you|thanks)(?:\s+\S+){0,4}[\s\W]*$",
    r"^(مع\s+السلامة|وداع[اً]?|bye|goodbye|au\s+revoir)(?:\s+\S+){0,3}[\s\W]*$",
    r"^(صباح\s+(الخير|النور)|مساء\s+(الخير|النور)|ليلة\s+سعيدة|صباحك\s+\S+|مساؤك\s+\S+)[\s\W]*$",
]


def classify_path(question: str, *, is_admin: bool) -> PathType:
    """Classify a WS turn's path before the graph runs.

    Admin endpoint always reports `admin` regardless of educational intent —
    admin and customer paths must remain distinguishable for capacity planning.
    """
    if is_admin:
        return "admin"
    q = (question or "").strip()
    if not q:
        return "unknown"
    for pat in _GREETING_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return "general_chat"
    for pat in _EDUCATIONAL_PATTERNS:
        if re.search(pat, q, re.IGNORECASE | re.UNICODE):
            return "educational"
    return "general_chat"


@dataclass
class WsTurnSpan:
    """Mutable span handle for one WS chat turn.

    Routers obtain this from `ws_chat_turn(...)` (async context) or
    `open_ws_turn(...)` / `close_ws_turn(...)` (manual open/close, used when
    re-indenting the live router would be more risk than benefit). All
    mutators are no-ops if the underlying tracer is unavailable.
    """

    request_id: str
    path_type: PathType
    user_id: int | None
    conversation_id: int | None
    is_admin: bool
    started_at: float = field(default_factory=time.perf_counter)
    fallback_used: bool = False
    streaming_mode: str = "ainvoke"
    terminal_event_type: str = "unknown"
    span_id: str | None = None
    trace_id: str | None = None
    _span_ctx: Any = None  # opaque TraceContext from UnifiedObservabilityService
    _closed: bool = False
    _cv_token: Any = None  # contextvars.Token used to unbind on close

    def mark_fallback(self, mode: str = "local_graph") -> None:
        self.fallback_used = True
        self.streaming_mode = mode
        if self.path_type != "admin":
            # The FALLBACK path label takes precedence for capacity metrics
            # but we keep `educational` / `general_chat` available via the
            # original tag on the span for finer breakdowns.
            self.path_type = "fallback"

    def set_intent(self, intent: str) -> None:
        if self.path_type in {"unknown", "general_chat"} and intent == "educational":
            self.path_type = "educational"

    def set_conversation_id(self, conversation_id: int | None) -> None:
        if conversation_id is not None and self.conversation_id is None:
            self.conversation_id = conversation_id

    def set_terminal(self, event_type: str) -> None:
        self.terminal_event_type = event_type

    @property
    def latency_ms(self) -> float:
        return (time.perf_counter() - self.started_at) * 1000.0


# Context var so deeper layers (orchestrator_client fallback chain,
# local_graph nodes) can locate the active turn handle without taking
# a parameter from the router.
_current_turn: contextvars.ContextVar[WsTurnSpan | None] = contextvars.ContextVar(
    "ws_chat_turn_span", default=None
)


def get_current_turn() -> WsTurnSpan | None:
    """Return the active `WsTurnSpan` for the current task, if any."""
    return _current_turn.get()


def mark_fallback_used(mode: str = "local_graph") -> None:
    """Convenience: deeper layers call this when the local fallback runs.

    No-op outside an active WS turn (e.g. unit tests, HTTP-only paths).
    """
    handle = _current_turn.get()
    if handle is not None:
        with contextlib.suppress(Exception):  # pragma: no cover
            handle.mark_fallback(mode)


def _safe_obs():
    try:
        from app.telemetry.unified_observability import get_unified_observability

        return get_unified_observability()
    except Exception:  # pragma: no cover - observability never blocks chat
        logger.debug("path_observer.obs_unavailable", exc_info=True)
        return None


def _bind_current(handle: WsTurnSpan) -> contextvars.Token:
    return _current_turn.set(handle)


def _unbind_current(token: contextvars.Token | None) -> None:
    if token is None:
        return
    with contextlib.suppress(Exception):  # pragma: no cover
        _current_turn.reset(token)


def open_ws_turn(
    *,
    user_id: int | None,
    conversation_id: int | None,
    is_admin: bool,
    question: str,
    request_id: str | None = None,
) -> WsTurnSpan:
    """Manual variant of `ws_chat_turn` for code paths that cannot be
    re-indented under an `async with` block (e.g. the existing customer/admin
    WS routers' per-turn structure). The caller MUST eventually call
    `close_ws_turn(handle, status=...)` — typically inside the per-turn
    `finally:` block, right next to `_emit_terminal_frames(...)`.
    """
    rid = (request_id or str(uuid.uuid4()))[:64]
    initial_path: PathType = classify_path(question, is_admin=is_admin)
    handle = WsTurnSpan(
        request_id=rid,
        path_type=initial_path,
        user_id=user_id,
        conversation_id=conversation_id,
        is_admin=is_admin,
    )

    obs = _safe_obs()
    if obs is not None:
        try:
            span_ctx = obs.start_trace(
                operation_name="ws.chat.turn",
                tags={
                    "ws.endpoint": "/admin/api/chat/ws" if is_admin else "/api/chat/ws",
                    "ws.request_id": rid,
                    "user.id": user_id if user_id is not None else "anonymous",
                    "user.is_admin": is_admin,
                    "conversation.id": conversation_id
                    if conversation_id is not None
                    else "pending",
                    "chat.path_type": initial_path,
                    "service.name": "cogniforge-monolith",
                },
            )
            handle._span_ctx = span_ctx
            handle.span_id = getattr(span_ctx, "span_id", None)
            handle.trace_id = getattr(span_ctx, "trace_id", None)
        except Exception:  # pragma: no cover
            logger.debug("path_observer.start_trace_failed", exc_info=True)
    # Bind so deeper layers (orchestrator_client, local_graph) can find this
    # turn via `get_current_turn()` / `mark_fallback_used()`. The router's
    # `close_ws_turn` resets the ContextVar.
    handle._cv_token = _bind_current(handle)
    return handle


def close_ws_turn(handle: WsTurnSpan, *, status: str = "OK") -> None:
    """Close the span (idempotent) and emit terminal metrics.

    Safe to call exactly once per turn from the router's `finally:` block.
    """
    if handle._closed:
        return
    handle._closed = True
    _unbind_current(handle._cv_token)
    handle._cv_token = None
    obs = _safe_obs()
    span_ctx = handle._span_ctx
    if obs is not None and span_ctx is not None:
        with contextlib.suppress(Exception):  # pragma: no cover
            obs.add_span_event(
                span_id=span_ctx.span_id,
                event_name="ws.chat.turn.terminal",
                attributes={
                    "chat.path_type": handle.path_type,
                    "chat.terminal_event": handle.terminal_event_type,
                    "chat.fallback_used": handle.fallback_used,
                    "chat.streaming_mode": handle.streaming_mode,
                    "conversation.id": handle.conversation_id
                    if handle.conversation_id is not None
                    else "pending",
                },
            )
        with contextlib.suppress(Exception):  # pragma: no cover
            obs.end_span(
                span_id=span_ctx.span_id,
                status=status if handle.terminal_event_type != "error" else "ERROR",
                metrics={
                    "duration_ms": handle.latency_ms,
                    "fallback_used": 1.0 if handle.fallback_used else 0.0,
                },
            )

    if obs is not None:
        labels = {
            "path_type": handle.path_type if handle.path_type in _VALID_PATHS else "unknown",
            "terminal": handle.terminal_event_type
            if handle.terminal_event_type in {"assistant_final", "error", "unknown"}
            else "unknown",
            "is_admin": "true" if handle.is_admin else "false",
        }
        with contextlib.suppress(Exception):  # pragma: no cover
            obs.record_metric(
                name="ws.chat.turn.duration_seconds",
                value=handle.latency_ms / 1000.0,
                labels=labels,
                trace_id=handle.trace_id,
                span_id=handle.span_id,
            )
        with contextlib.suppress(Exception):  # pragma: no cover
            obs.increment_counter(
                name="ws.chat.terminal_events.total",
                labels=labels,
            )
        if handle.fallback_used:
            with contextlib.suppress(Exception):  # pragma: no cover
                obs.increment_counter(
                    name="ws.chat.fallback.total",
                    labels={
                        "path_type": handle.path_type,
                        "is_admin": "true" if handle.is_admin else "false",
                    },
                )

    # Mirror to OpenTelemetry SDK if the observability stack is configured.
    # No-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset — see otel_setup.py.
    _emit_to_otel(handle)


def _emit_to_otel(handle: WsTurnSpan) -> None:
    """Mirror per-turn metrics into the OpenTelemetry SDK so they flow to
    Tempo + Prometheus via the OTel collector. Pure no-op when OTel
    is not initialized."""
    try:
        from app.telemetry import otel_setup as _otel
    except Exception:  # pragma: no cover
        return
    if not _otel.is_initialized():
        return
    instruments = _otel.get_metrics()
    attrs = {
        "path_type": handle.path_type if handle.path_type in _VALID_PATHS else "unknown",
        "terminal": handle.terminal_event_type
        if handle.terminal_event_type in {"assistant_final", "error", "unknown"}
        else "unknown",
        "is_admin": "true" if handle.is_admin else "false",
    }
    histogram = instruments.get("ws_chat_turn_duration_seconds")
    counter_terminal = instruments.get("ws_chat_terminal_events_total")
    counter_fallback = instruments.get("ws_chat_fallback_total")
    with contextlib.suppress(Exception):  # pragma: no cover
        if histogram is not None:
            histogram.record(handle.latency_ms / 1000.0, attributes=attrs)
    with contextlib.suppress(Exception):  # pragma: no cover
        if counter_terminal is not None:
            counter_terminal.add(1, attributes=attrs)
    if handle.fallback_used:
        with contextlib.suppress(Exception):  # pragma: no cover
            if counter_fallback is not None:
                counter_fallback.add(
                    1,
                    attributes={
                        "path_type": handle.path_type,
                        "is_admin": "true" if handle.is_admin else "false",
                    },
                )


@asynccontextmanager
async def ws_chat_turn(
    *,
    user_id: int | None,
    conversation_id: int | None,
    is_admin: bool,
    question: str,
    request_id: str | None = None,
):
    """Async-context variant of `open_ws_turn` / `close_ws_turn`.

    Yields a `WsTurnSpan` the router can mutate. On exit the span is closed
    and metrics are emitted exactly once. Behavior on failure: the context
    still yields a real `WsTurnSpan`; underlying tracing calls become
    no-ops. The chat turn never sees an observability exception.
    """
    handle = open_ws_turn(
        user_id=user_id,
        conversation_id=conversation_id,
        is_admin=is_admin,
        question=question,
        request_id=request_id,
    )
    status = "OK"
    try:
        yield handle
    except Exception:
        status = "ERROR"
        raise
    finally:
        close_ws_turn(handle, status=status)
