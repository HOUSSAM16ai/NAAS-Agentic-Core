"""
Skills Composition Pipeline — الخطوة 11.

يُنفِّذ هذا الوحدة مبدأ Skills Architecture: كل قدرة ذكاء اصطناعي هي Skill مستقلة
تُستدعى عبر HTTP حقيقي مع X-Correlation-ID للتتبع الموزع.

مسار الطلب:
  /compose → PlanningSkill.plan() → ResearchSkill.retrieve() → ReasoningSkill.reason()
           → ComposedResponse (مُركَّب من نتائج الـ 3 Skills)

قواعد الـ Skills (D-038):
  - كل Skill تُستدعى عبر httpx.AsyncClient مع timeout=10s
  - X-Correlation-ID مُرسَل في كل طلب للتتبع الموزع
  - X-Service-Token مُرسَل لـ planning-agent (يتطلب JWT auth)
  - Fallback mode إلزامي عند تعذر الوصول لأي Skill
  - كل استدعاء يُسجَّل في Prometheus (cogniforge_pipeline_*)

إصلاح ISS-042 (الخطوة 11):
  - planning-agent يتطلب X-Service-Token (JWT موقَّع بـ SECRET_KEY المشترك)
  - orchestrator يُولِّد الـ token عند كل استدعاء (exp=5min)
  - SECRET_KEY مُشترك بين orchestrator و planning-agent عبر env var
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field

import httpx

from microservices.orchestrator_service.src.core.config import get_settings

logger = logging.getLogger("skills_pipeline")

# ── ثوابت الـ Pipeline ────────────────────────────────────────────────────────
# ISS-042 (Step 11): رُفع إلى 55s — planning (DSPy 3x LLM) و reasoning (MCTS+LLM) يحتاجان ~30-45s
# جميع الـ Skills تعمل بالتوازي الكامل لتقليل الزمن الإجمالي
_SKILL_TIMEOUT_SECONDS: float = 55.0
_CALLER_ID: str = "orchestrator-service"


def _generate_service_token(secret_key: str) -> str:
    """
    يُولِّد JWT service token لاستدعاء planning-agent.

    planning-agent يتحقق من:
      - sub == "api-gateway"
      - توقيع HS256 بـ SECRET_KEY المشترك
      - exp لم ينتهِ

    يُستخدم هذا الـ token في X-Service-Token header.
    """
    try:
        import time as _time

        import jwt

        payload = {
            "sub": "api-gateway",
            "iss": _CALLER_ID,
            "iat": int(_time.time()),
            "exp": int(_time.time()) + 300,  # 5 دقائق
        }
        return jwt.encode(payload, secret_key, algorithm="HS256")
    except Exception as exc:
        logger.warning("Service token generation failed: %s — using empty token", exc)
        return ""


# ── نماذج البيانات ────────────────────────────────────────────────────────────


@dataclass
class SkillResult:
    """نتيجة استدعاء Skill واحدة."""

    skill: str
    status: str  # "success" | "fallback" | "error"
    data: dict[str, object]
    duration_ms: float
    error: str | None = None


@dataclass
class PipelineResult:
    """النتيجة المُركَّبة من جميع Skills."""

    correlation_id: str
    query: str
    plan: SkillResult
    research: SkillResult
    reasoning: SkillResult
    composed_answer: str
    total_duration_ms: float
    skills_active: list[str] = field(default_factory=list)
    pipeline_mode: str = "full"  # "full" | "partial" | "fallback"
    composition_confidence: float = 0.0  # D-110: ثقة التركيب [0,1]


# ── استدعاءات الـ Skills ──────────────────────────────────────────────────────


async def _call_planning_skill(
    query: str,
    correlation_id: str,
    client: httpx.AsyncClient,
    trace_headers: dict[str, str] | None = None,
) -> SkillResult:
    """
    يستدعي planning-agent عبر HTTP لتوليد خطة استراتيجية.

    المدخلات:
        query: سؤال الطالب أو المهمة المطلوبة
        correlation_id: معرف التتبع الموزع
        client: httpx.AsyncClient مُشترك

    العائد:
        SkillResult مع plan_steps و subject و difficulty
    """
    settings = get_settings()
    url = f"{settings.PLANNING_AGENT_URL}/execute"
    start = time.monotonic()

    # ISS-042: planning-agent يتطلب X-Service-Token (JWT HS256)
    service_token = _generate_service_token(settings.SECRET_KEY)

    try:
        headers = {
            "X-Correlation-ID": correlation_id,
            "X-Service-Token": service_token,
        }
        if trace_headers:
            headers.update(trace_headers)
        response = await client.post(
            url,
            json={
                "caller_id": _CALLER_ID,
                "target_service": "planning_agent",
                "action": "generate_plan",
                "payload": {"query": query, "subject": "general", "difficulty": "medium"},
            },
            headers=headers,
            timeout=_SKILL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        duration_ms = (time.monotonic() - start) * 1000

        if body.get("status") == "success" and body.get("data"):
            return SkillResult(
                skill="planning",
                status="success",
                data=body["data"],
                duration_ms=duration_ms,
            )

        return SkillResult(
            skill="planning",
            status="fallback",
            data={"plan_steps": [f"خطة افتراضية لـ: {query}"], "subject": "general"},
            duration_ms=duration_ms,
            error=body.get("error"),
        )

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("planning-agent unreachable: %s", exc)
        return SkillResult(
            skill="planning",
            status="fallback",
            data={"plan_steps": [f"خطة افتراضية لـ: {query}"], "subject": "general"},
            duration_ms=duration_ms,
            error=str(exc),
        )
    except httpx.HTTPStatusError as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error("planning-agent HTTP error %s: %s", exc.response.status_code, exc)
        return SkillResult(
            skill="planning",
            status="error",
            data={},
            duration_ms=duration_ms,
            error=f"HTTP {exc.response.status_code}",
        )


async def _call_research_skill(
    query: str,
    plan_context: str,
    correlation_id: str,
    client: httpx.AsyncClient,
    trace_headers: dict[str, str] | None = None,
) -> SkillResult:
    """
    يستدعي research-agent عبر HTTP لاسترجاع المعلومات ذات الصلة.

    المدخلات:
        query: سؤال الطالب
        plan_context: سياق الخطة من planning-agent
        correlation_id: معرف التتبع الموزع
        client: httpx.AsyncClient مُشترك

    العائد:
        SkillResult مع results و sources
    """
    settings = get_settings()
    url = f"{settings.RESEARCH_AGENT_URL}/execute"
    start = time.monotonic()
    service_token = _generate_service_token(settings.SECRET_KEY)

    try:
        headers = {
            "X-Correlation-ID": correlation_id,
            "X-Service-Token": service_token,
        }
        if trace_headers:
            headers.update(trace_headers)
        response = await client.post(
            url,
            json={
                "caller_id": _CALLER_ID,
                "target_service": "research_agent",
                "action": "search",
                "payload": {
                    "query": query,
                    "context": plan_context,
                    "max_results": 5,
                },
            },
            headers=headers,
            timeout=_SKILL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        duration_ms = (time.monotonic() - start) * 1000

        if body.get("status") == "success" and body.get("data"):
            return SkillResult(
                skill="research",
                status="success",
                data=body["data"],
                duration_ms=duration_ms,
            )

        return SkillResult(
            skill="research",
            status="fallback",
            data={"results": [], "sources": [], "summary": f"لا توجد نتائج بحث لـ: {query}"},
            duration_ms=duration_ms,
            error=body.get("error"),
        )

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("research-agent unreachable: %s", exc)
        return SkillResult(
            skill="research",
            status="fallback",
            data={"results": [], "sources": [], "summary": f"بحث افتراضي لـ: {query}"},
            duration_ms=duration_ms,
            error=str(exc),
        )
    except httpx.HTTPStatusError as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error("research-agent HTTP error %s: %s", exc.response.status_code, exc)
        return SkillResult(
            skill="research",
            status="error",
            data={},
            duration_ms=duration_ms,
            error=f"HTTP {exc.response.status_code}",
        )


async def _call_reasoning_skill(
    query: str,
    context: str,
    correlation_id: str,
    client: httpx.AsyncClient,
    trace_headers: dict[str, str] | None = None,
) -> SkillResult:
    """
    يستدعي reasoning-agent عبر HTTP للتفكير العميق (MCTS + LLM).

    المدخلات:
        query: سؤال الطالب
        context: السياق المُجمَّع من planning + research
        correlation_id: معرف التتبع الموزع
        client: httpx.AsyncClient مُشترك

    العائد:
        SkillResult مع answer و confidence
    """
    settings = get_settings()
    url = f"{settings.REASONING_AGENT_URL}/execute"
    start = time.monotonic()
    service_token = _generate_service_token(settings.SECRET_KEY)

    try:
        headers = {
            "X-Correlation-ID": correlation_id,
            "X-Service-Token": service_token,
        }
        if trace_headers:
            headers.update(trace_headers)
        response = await client.post(
            url,
            json={
                "caller_id": _CALLER_ID,
                "target_service": "reasoning_agent",
                "action": "reason",
                "payload": {"query": query, "context": context},
            },
            headers=headers,
            timeout=_SKILL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        duration_ms = (time.monotonic() - start) * 1000

        if body.get("status") == "success" and body.get("data"):
            return SkillResult(
                skill="reasoning",
                status="success",
                data=body["data"],
                duration_ms=duration_ms,
            )

        return SkillResult(
            skill="reasoning",
            status="fallback",
            data={"answer": f"إجابة افتراضية لـ: {query}", "confidence": 0.0},
            duration_ms=duration_ms,
            error=body.get("error"),
        )

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning("reasoning-agent unreachable: %s", exc)
        return SkillResult(
            skill="reasoning",
            status="fallback",
            data={"answer": f"تفكير افتراضي لـ: {query}", "confidence": 0.0},
            duration_ms=duration_ms,
            error=str(exc),
        )
    except httpx.HTTPStatusError as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error("reasoning-agent HTTP error %s: %s", exc.response.status_code, exc)
        return SkillResult(
            skill="reasoning",
            status="error",
            data={},
            duration_ms=duration_ms,
            error=f"HTTP {exc.response.status_code}",
        )


# ── دالة التركيب ──────────────────────────────────────────────────────────────


def _compose_answer(
    query: str,
    plan: SkillResult,
    research: SkillResult,
    reasoning: SkillResult,
) -> tuple[str, float]:
    """
    D-110 (Real Synthesis): تركيب حقيقي مرتّب — ليس «أول-ناجح-يفوز».

    بدل انتقاء ناتج واحد، نَدمج النواتج الناجحة في إجابة واحدة مرتّبة:
      - reasoning (الحل/التفكير العميق) هو الجوهر إن نجح.
      - research (المراجع/الملخص) يُضاف كسياق داعم إن نجح ووُجد جوهر.
      - plan (الخطة) يُضاف كهيكل إن لم يوجد جوهر أقوى.
    ويُرجِع `composition_confidence ∈ [0,1]` دالةً من عدد النواتج الناجحة
    وتداخلها (reasoning+research معاً = ثقة أعلى). حتمي، fail-open.
    """
    successes = {s.skill: s for s in (plan, research, reasoning) if s.status == "success"}
    reasoning_answer = ""
    if reasoning.status == "success":
        reasoning_answer = str(reasoning.data.get("answer", "")).strip()

    research_summary = ""
    research_results: list[object] = []
    if research.status == "success":
        research_summary = str(research.data.get("summary", "")).strip()
        rr = research.data.get("results", [])
        research_results = list(rr) if isinstance(rr, list) else []

    plan_steps = plan.data.get("plan_steps", []) if isinstance(plan.data, dict) else []

    # ── التركيب المرتّب ──────────────────────────────────────────────────────
    core = reasoning_answer
    if not core and research_summary:
        core = research_summary
    if not core and research_results:
        core = "نتائج البحث: " + " | ".join(str(r) for r in research_results[:3])

    parts: list[str] = []
    if core:
        parts.append(core)
        # دمج المراجع الداعمة فقط حين يكون الجوهر من reasoning (تجنّب التكرار).
        if reasoning_answer and research_summary and research_summary != reasoning_answer:
            parts.append(f"\n\nمراجع داعمة:\n{research_summary}")
    elif plan_steps:
        steps_text = "\n".join(f"- {s}" for s in plan_steps[:5])
        parts.append(f"خطة للإجابة على '{query}':\n{steps_text}")

    composed = "\n".join(parts).strip()

    # ── ثقة التركيب (مبنية على النواتج الناجحة فعلاً، لا fallback data) ───────
    n = len(successes)
    if not composed:
        confidence = 0.1
        composed = f"لم أتمكن من معالجة طلبك: {query}"
    elif n == 0:
        # لا skill نجح — المحتوى من fallback data فقط ⇒ ثقة منخفضة صريحة.
        confidence = 0.25
    elif n >= 3:
        confidence = 0.9
    elif n == 2:
        # reasoning ضمن الناجحين ⇒ ثقة أعلى (حل فعلي لا مجرد بحث).
        confidence = 0.78 if "reasoning" in successes else 0.68
    else:
        confidence = 0.55 if "reasoning" in successes else 0.45

    return composed, round(confidence, 3)


def _determine_pipeline_mode(
    plan: SkillResult,
    research: SkillResult,
    reasoning: SkillResult,
) -> tuple[str, list[str]]:
    """
    يُحدِّد وضع الـ Pipeline بناءً على نتائج الـ Skills.

    العائد:
        tuple[mode, active_skills]:
          mode: "full" | "partial" | "fallback"
          active_skills: قائمة الـ Skills التي نجحت
    """
    active = [s.skill for s in (plan, research, reasoning) if s.status == "success"]

    if len(active) == 3:
        return "full", active
    if len(active) >= 1:
        return "partial", active
    return "fallback", []


# ── الدالة الرئيسية ───────────────────────────────────────────────────────────


async def run_skills_pipeline(
    query: str,
    correlation_id: str | None = None,
    trace_context: object | None = None,
) -> PipelineResult:
    """
    يُشغِّل Skills Composition Pipeline الكامل.

    المسار:
      1. PlanningSkill.plan(query)          → خطة استراتيجية
      2. ResearchSkill.retrieve(query, plan) → معلومات ذات صلة
      3. ReasoningSkill.reason(query, ctx)   → تفكير عميق (MCTS + LLM)
      4. compose(plan, research, reasoning)  → إجابة مُركَّبة

    الخطوات 1 و 2 تعمل بالتوازي (asyncio.gather) لتقليل الزمن الكلي.
    الخطوة 3 تعتمد على نتائج 1 و 2 كسياق.

    المدخلات:
        query: سؤال الطالب أو المهمة
        correlation_id: معرف التتبع (يُولَّد تلقائياً إذا لم يُعطَ)

    العائد:
        PipelineResult مع نتائج الـ 3 Skills والإجابة المُركَّبة
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    pipeline_start = time.monotonic()
    logger.info("pipeline_start correlation_id=%s query_len=%d", correlation_id, len(query))

    async with httpx.AsyncClient() as client:
        # ── المرحلة الموحدة: Planning + Research + Reasoning بالتوازي الكامل ─
        # ISS-042 (Step 11): الـ 3 Skills تعمل بالتوازي لتقليل الزمن الإجمالي.
        # reasoning يستقبل السياق الأولي (query فقط) ويعمل بالتوازي مع planning+research.
        # هذا يُقلِّل الزمن من (planning + research + reasoning) إلى max(الثلاثة).
        trace_headers = {}
        if trace_context and hasattr(trace_context, "to_headers"):
            trace_headers = trace_context.to_headers()

        plan_result, research_result, reasoning_result = await asyncio.gather(
            _call_planning_skill(query, correlation_id, client, trace_headers=trace_headers),
            _call_research_skill(query, "", correlation_id, client, trace_headers=trace_headers),
            _call_reasoning_skill(query, "", correlation_id, client, trace_headers=trace_headers),
        )

    # ── التركيب النهائي (D-110: تركيب مرتّب + ثقة) ────────────────────────────
    total_duration_ms = (time.monotonic() - pipeline_start) * 1000
    composed_answer, composition_confidence = _compose_answer(
        query, plan_result, research_result, reasoning_result
    )
    pipeline_mode, active_skills = _determine_pipeline_mode(
        plan_result, research_result, reasoning_result
    )
    with contextlib.suppress(Exception):
        from microservices.orchestrator_service.src.core.prom_metrics import (
            set_composition_confidence,
        )

        set_composition_confidence(composition_confidence)

    logger.info(
        "pipeline_complete correlation_id=%s mode=%s active_skills=%s "
        "confidence=%.2f duration_ms=%.1f",
        correlation_id,
        pipeline_mode,
        active_skills,
        composition_confidence,
        total_duration_ms,
    )

    return PipelineResult(
        correlation_id=correlation_id,
        query=query,
        plan=plan_result,
        research=research_result,
        reasoning=reasoning_result,
        composed_answer=composed_answer,
        total_duration_ms=total_duration_ms,
        skills_active=active_skills,
        pipeline_mode=pipeline_mode,
        composition_confidence=composition_confidence,
    )
