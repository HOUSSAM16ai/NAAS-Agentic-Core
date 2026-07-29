"""notation-service — the API-first mathematical-notation Skill (D-185).

Why this service exists
-----------------------
A real student asked **«ماذا نقصد بحرف C»** — "what does the letter C mean?" — about a
symbol the tutor itself had just printed on screen. Every matching surface in the platform
was keyed on the *concept name* ("التوافيق"/`combinaison`), never on the *symbol*, so the
student had to already know the concept's name in order to ask what it meant. The question
fell through every deterministic layer and the tutor re-dumped the derivation the student
had not understood (ISS-138).

This service makes that class of failure impossible: **the system can define every symbol
it prints**, over an explicit HTTP contract rather than a branch buried in the monolith.
Enforced in CI by `scripts/fitness/check_notation_definable.py`.

Contract:
  POST /resolve → ResolveResponse   (free student text → matched symbol or null)
  POST /define  → DefineResponse    (symbol → definition + neutral example)
  GET  /symbols → SymbolsResponse   (the full registry)
  GET  /health  → HealthResponse    (real readiness fields, not just {"status":"ok"})
  GET  /metrics → Prometheus text format

Skill rules (CLAUDE.md §0.5):
  - single responsibility: deterministic notation resolution — never an LLM
  - no import from another microservice or the monolith (vendored registry)
  - fail-open: an unknown symbol returns found=false, never a 500
  - every call recorded in Prometheus
  - works with no DB and no API keys

Socratic contract (D-113 → D-155): a definition is not an answer. Every `example` in the
registry is neutral (`C(5,2)`), never the numbers of the exercise the student is solving,
so this endpoint can never leak "14" or "165".
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from pydantic import BaseModel, Field

from microservices.notation_service.prom_metrics import (
    REGISTRY,
    dec_active,
    inc_active,
    record_definition,
    record_request,
    record_resolution,
    set_startup_info,
)
from microservices.notation_service.src.notation import (
    NOTATION_REGISTRY,
    REGISTRY_VERSION,
    NotationEntry,
    all_symbols,
    define,
    resolve,
)

_SERVICE_VERSION = "1.0.0"
_STEP = "14"


# ── API models ────────────────────────────────────────────────────────────────


class SymbolPayload(BaseModel):
    """رمز مُعرَّف كما يُسلَّم عبر العقد."""

    symbol: str
    title: str
    definition: str
    example: str
    concept_id: str | None = None
    property_id: str | None = None


class ResolveRequest(BaseModel):
    """نصّ الطالب الحرّ كما وصل — بلا أي معالجة مسبقة."""

    text: str = Field(..., min_length=1, max_length=2000)


class ResolveResponse(BaseModel):
    """نتيجة التحويل — `found=false` جواب مشروع لا خطأ."""

    found: bool
    symbol: SymbolPayload | None = None
    registry_version: str
    duration_ms: float
    trace_id: str


class DefineRequest(BaseModel):
    """استعلام تعريف رمزٍ بعينه (`C`, `n!`, `P_A(B)` …)."""

    symbol: str = Field(..., min_length=1, max_length=64)


class DefineResponse(BaseModel):
    """تعريف رمز — أو `found=false` مع سبب مُهيكَل."""

    found: bool
    symbol: SymbolPayload | None = None
    error: dict[str, str] | None = None
    registry_version: str
    duration_ms: float
    trace_id: str


class SymbolsResponse(BaseModel):
    """السجلّ كاملاً — يُغذّي بوّابات CI والوكلاء المستقبليين."""

    symbols: list[SymbolPayload]
    count: int
    registry_version: str


class HealthResponse(BaseModel):
    """فحص الصحّة بحقول جاهزية حقيقية — «Degraded ≠ Dead» (CLAUDE.md §0)."""

    status: str
    service: str
    step: str
    version: str
    registry_version: str
    symbols_loaded: int
    startup_state: str
    llm_backend: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _payload(entry: NotationEntry) -> SymbolPayload:
    """يحوّل إدخال السجلّ إلى حمولة العقد."""
    return SymbolPayload(
        symbol=entry.symbol,
        title=entry.title,
        definition=entry.definition,
        example=entry.example,
        concept_id=entry.concept_id,
        property_id=entry.property_id,
    )


def _trace(correlation_id: str | None) -> str:
    """يمرّر `X-Correlation-ID` الوارد أو يولّد واحداً — التتبّع لا ينقطع أبداً."""
    return correlation_id or str(uuid.uuid4())


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """يثبّت معلومات الإقلاع (لا إحماء — السجلّ stdlib خالص)."""
    set_startup_info(
        step=_STEP,
        version=_SERVICE_VERSION,
        registry_version=REGISTRY_VERSION,
        symbols=len(NOTATION_REGISTRY),
    )
    yield


app = FastAPI(
    title="notation-service",
    description="API-first deterministic mathematical-notation Skill — D-185",
    version=_SERVICE_VERSION,
    lifespan=lifespan,
)


@app.post("/resolve", response_model=ResolveResponse)
async def resolve_endpoint(
    request: ResolveRequest,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
) -> ResolveResponse:
    """يحوّل سؤال الطالب الحرّ إلى رمز مُعرَّف — حتمي، fail-open."""
    inc_active()
    t0 = time.monotonic()
    try:
        entry = resolve(request.text)
        duration = time.monotonic() - t0
        record_resolution(entry.symbol if entry else None)
        record_request("/resolve", "ok", duration)
        return ResolveResponse(
            found=entry is not None,
            symbol=_payload(entry) if entry else None,
            registry_version=REGISTRY_VERSION,
            duration_ms=duration * 1000,
            trace_id=_trace(x_correlation_id),
        )
    finally:
        dec_active()


@app.post("/define", response_model=DefineResponse)
async def define_endpoint(
    request: DefineRequest,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
) -> DefineResponse:
    """يُرجع تعريف رمزٍ بعينه — رمز غير معروف ⇒ خطأ مُهيكَل لا استثناء."""
    inc_active()
    t0 = time.monotonic()
    trace_id = _trace(x_correlation_id)
    try:
        entry = define(request.symbol)
        duration = time.monotonic() - t0
        record_definition(entry is not None)
        record_request("/define", "ok" if entry else "not_found", duration)
        if entry is None:
            return DefineResponse(
                found=False,
                error={
                    "code": "NOTATION_SYMBOL_UNKNOWN",
                    "message": f"الرمز {request.symbol!r} غير مُعرَّف في السجلّ.",
                    "trace_id": trace_id,
                },
                registry_version=REGISTRY_VERSION,
                duration_ms=duration * 1000,
                trace_id=trace_id,
            )
        return DefineResponse(
            found=True,
            symbol=_payload(entry),
            registry_version=REGISTRY_VERSION,
            duration_ms=duration * 1000,
            trace_id=trace_id,
        )
    finally:
        dec_active()


@app.get("/symbols", response_model=SymbolsResponse)
async def symbols_endpoint() -> SymbolsResponse:
    """يُرجع السجلّ كاملاً — مصدر بوّابة «لا رمز يتيم» والوكلاء."""
    return SymbolsResponse(
        symbols=[_payload(entry) for entry in NOTATION_REGISTRY],
        count=len(NOTATION_REGISTRY),
        registry_version=REGISTRY_VERSION,
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """فحص صحّة بحقول جاهزية — سجلّ فارغ يعني `degraded` لا `healthy`."""
    loaded = len(all_symbols())
    return HealthResponse(
        status="healthy" if loaded else "degraded",
        service="notation-service",
        step=_STEP,
        version=_SERVICE_VERSION,
        registry_version=REGISTRY_VERSION,
        symbols_loaded=loaded,
        startup_state="ready" if loaded else "empty_registry",
        llm_backend="none",
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus metrics endpoint."""
    return generate_latest(REGISTRY).decode("utf-8")
