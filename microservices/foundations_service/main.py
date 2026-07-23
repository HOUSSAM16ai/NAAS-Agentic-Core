"""foundations-service — the API-first "first roots" compute Skill (D-183).

An independent microservice exposing the verified pre-programming substrate
(logic, mathematics, theory of computation) as a deterministic HTTP compute
surface. It never calls an LLM: every result comes from a dependency-free engine
(CLAUDE.md §0: "symbolic truth before language").

Contract:
  POST /compute → ComputeResponse   (deterministic {domain, operation, args})
  GET  /health  → HealthResponse
  GET  /metrics → Prometheus text format

Skill rules (CLAUDE.md §0.5):
  - single responsibility: deterministic foundations compute
  - no import from another microservice or the monolith (vendored engines)
  - fail-open: a domain violation returns ok=false + error, never a 500
  - every call recorded in Prometheus
  - works with no DB and no API keys
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from pydantic import BaseModel, Field

from microservices.foundations_service.prom_metrics import (
    REGISTRY,
    dec_active,
    inc_active,
    record_compute,
    record_compute_error,
    record_request,
    set_startup_info,
)
from microservices.foundations_service.src.dispatch import (
    ComputeError,
    compute,
    supported_domains,
)
from microservices.foundations_service.src.foundations.errors import FoundationsError

_SERVICE_VERSION = "1.0.0"
_STEP = "13"


# ── API models ────────────────────────────────────────────────────────────────


class ComputeRequest(BaseModel):
    """Deterministic compute request — domain + operation + structured args."""

    domain: str = Field(..., min_length=1, max_length=40)
    operation: str = Field(..., min_length=1, max_length=40)
    args: dict[str, Any] = Field(default_factory=dict)


class ComputeResponse(BaseModel):
    """Deterministic compute response — result or a reported error (never raises)."""

    domain: str
    operation: str
    ok: bool
    result: Any = None
    error: str | None = None
    duration_ms: float


class HealthResponse(BaseModel):
    """Health probe."""

    status: str
    service: str
    step: str
    version: str
    domains: list[str]
    llm_backend: str


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Register startup info at boot (no warmup — pure stdlib engines)."""
    set_startup_info(step=_STEP, version=_SERVICE_VERSION, domains=",".join(supported_domains()))
    yield


app = FastAPI(
    title="foundations-service",
    description="API-first deterministic 'first roots' compute Skill — D-183",
    version=_SERVICE_VERSION,
    lifespan=lifespan,
)


@app.post("/compute", response_model=ComputeResponse)
async def compute_endpoint(request: ComputeRequest) -> ComputeResponse:
    """Run one deterministic foundations operation (fail-open)."""
    inc_active()
    t0 = time.monotonic()
    try:
        try:
            result = compute(request.domain, request.operation, request.args)
            duration = time.monotonic() - t0
            record_compute(request.domain, request.operation, "ok", duration)
            record_request("/compute", "ok", duration)
            return ComputeResponse(
                domain=request.domain,
                operation=request.operation,
                ok=True,
                result=result,
                duration_ms=duration * 1000,
            )
        except (ComputeError, FoundationsError, KeyError, TypeError, ValueError) as exc:
            duration = time.monotonic() - t0
            record_compute(request.domain, request.operation, "error", duration)
            record_compute_error(request.domain, type(exc).__name__)
            record_request("/compute", "error", duration)
            return ComputeResponse(
                domain=request.domain,
                operation=request.operation,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=duration * 1000,
            )
    finally:
        dec_active()


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health probe — always healthy (no external dependency)."""
    return HealthResponse(
        status="healthy",
        service="foundations-service",
        step=_STEP,
        version=_SERVICE_VERSION,
        domains=supported_domains(),
        llm_backend="none",
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus metrics endpoint."""
    return generate_latest(REGISTRY).decode("utf-8")
