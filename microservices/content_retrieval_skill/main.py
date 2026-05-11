"""
content-retrieval-skill — الخطوة 11.

Skill مستقلة لاسترجاع المحتوى التعليمي من knowledge_base/.

Contract:
  POST /retrieve  → RetrieveResponse
  GET  /health    → HealthResponse
  GET  /metrics   → Prometheus text format

قواعد الـ Skill (D-038):
  - هدف واحد: تصنيف النية + جلب المحتوى
  - لا تستورد من microservice آخر
  - Fallback mode إلزامي (قائمة فارغة عند الفشل)
  - كل استدعاء مُسجَّل في Prometheus
  - يعمل بدون DB (يقرأ من الملفات مباشرة)

ISS-038 (الإصلاح الجذري):
  - intent_classifier يمنع التفعيل الخاطئ
  - "تمرين" في سياق الشرح → explanation (لا استرجاع)
  - فقط نية الجلب الصريحة تُفعِّل الاسترجاع
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from pydantic import BaseModel, Field

from microservices.content_retrieval_skill.prom_metrics import (
    REGISTRY,
    record_request,
    set_kb_size,
    set_startup_info,
)
from microservices.content_retrieval_skill.src.intent_classifier import classify_intent
from microservices.content_retrieval_skill.src.retrieval_engine import (
    RetrievalQuery,
    retrieve,
)

# ── مسار knowledge_base ───────────────────────────────────────────────────────
_KB_ROOT = Path(os.environ.get("KB_ROOT", "/workspaces/NAAS-Agentic-Core/knowledge_base"))
_SERVICE_VERSION = "1.0.0"
_STEP = "11"


# ── نماذج الـ API ─────────────────────────────────────────────────────────────


class RetrieveRequest(BaseModel):
    """طلب الاسترجاع — contract ثابت."""

    question: str = Field(..., min_length=1, description="سؤال الطالب")
    subject: str | None = Field(None, description="المادة (math/physics/chemistry)")
    year: str | None = Field(None, description="السنة الدراسية (2020-2030)")
    max_results: int = Field(5, ge=1, le=20)


class ContentItemResponse(BaseModel):
    """وحدة محتوى في الاستجابة."""

    id: str
    title: str
    subject: str
    year: str
    tags: list[str]
    content_preview: str
    file_path: str


class RetrieveResponse(BaseModel):
    """استجابة الاسترجاع — contract ثابت."""

    intent: str
    intent_confidence: float
    intent_reason: str
    items: list[ContentItemResponse]
    total: int
    duration_ms: float
    kb_path: str
    query_subject: str | None
    query_year: str | None


class HealthResponse(BaseModel):
    """استجابة فحص الصحة."""

    status: str
    service: str
    step: str
    kb_path: str
    kb_files: int
    version: str


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """يُهيِّئ الـ Skill عند الإقلاع ويُسجِّل المقاييس."""
    kb_files = len(list(_KB_ROOT.glob("**/*.md"))) if _KB_ROOT.exists() else 0
    set_kb_size(kb_files)
    set_startup_info(step=_STEP, version=_SERVICE_VERSION, kb_path=str(_KB_ROOT))
    yield


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="content-retrieval-skill",
    description="Skill مستقلة لاسترجاع المحتوى التعليمي — الخطوة 11",
    version=_SERVICE_VERSION,
    lifespan=lifespan,
)


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_content(request: RetrieveRequest) -> RetrieveResponse:
    """
    يُصنِّف نية الطلب ويسترجع المحتوى المناسب.

    المسار:
      1. classify_intent(question) → intent
      2. إذا intent == "explanation" → إعادة قائمة فارغة فوراً
      3. إذا intent == "retrieval" → retrieve(query, kb_root)
      4. إذا intent == "unknown" → retrieve مع درجة ثقة منخفضة
    """
    t0 = time.monotonic()

    # ── تصنيف النية ───────────────────────────────────────────────────────────
    intent_result = classify_intent(request.question)

    # ── قرار الاسترجاع ────────────────────────────────────────────────────────
    if intent_result.intent == "explanation":
        duration_ms = (time.monotonic() - t0) * 1000
        record_request(status="skip", intent="explanation", duration_s=duration_ms / 1000)
        return RetrieveResponse(
            intent="explanation",
            intent_confidence=intent_result.confidence,
            intent_reason=intent_result.reason,
            items=[],
            total=0,
            duration_ms=duration_ms,
            kb_path=str(_KB_ROOT),
            query_subject=request.subject,
            query_year=request.year,
        )

    # ── استرجاع المحتوى ───────────────────────────────────────────────────────
    query = RetrievalQuery(
        question=request.question,
        intent=intent_result.intent,
        subject=request.subject,
        year=request.year,
        max_results=request.max_results,
    )
    result = retrieve(query, _KB_ROOT)

    duration_ms = (time.monotonic() - t0) * 1000
    status = "hit" if result.total > 0 else "miss"
    record_request(status=status, intent=intent_result.intent, duration_s=duration_ms / 1000)

    return RetrieveResponse(
        intent=intent_result.intent,
        intent_confidence=intent_result.confidence,
        intent_reason=intent_result.reason,
        items=[
            ContentItemResponse(
                id=item.id,
                title=item.title,
                subject=item.subject,
                year=item.year,
                tags=item.tags,
                content_preview=item.content_preview,
                file_path=item.file_path,
            )
            for item in result.items
        ],
        total=result.total,
        duration_ms=duration_ms,
        kb_path=result.kb_path,
        query_subject=result.query_subject,
        query_year=result.query_year,
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """فحص صحة الـ Skill."""
    kb_files = len(list(_KB_ROOT.glob("**/*.md"))) if _KB_ROOT.exists() else 0
    return HealthResponse(
        status="healthy",
        service="content-retrieval-skill",
        step=_STEP,
        kb_path=str(_KB_ROOT),
        kb_files=kb_files,
        version=_SERVICE_VERSION,
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus metrics endpoint."""
    return generate_latest(REGISTRY).decode("utf-8")
