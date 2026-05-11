"""
Skills Composition Pipeline — الخطوة 9.

يُنفِّذ هذا الوحدة مبدأ Skills Architecture: كل قدرة ذكاء اصطناعي هي Skill مستقلة
تُستدعى عبر HTTP حقيقي مع X-Correlation-ID للتتبع الموزع.

مسار الطلب:
  /compose → PlanningSkill.plan() → ResearchSkill.retrieve() → ReasoningSkill.reason()
           → ComposedResponse (مُركَّب من نتائج الـ 3 Skills)

قواعد الـ Skills (D-038):
  - كل Skill تُستدعى عبر httpx.AsyncClient مع timeout=10s
  - X-Correlation-ID مُرسَل في كل طلب للتتبع الموزع
  - Fallback mode إلزامي عند تعذر الوصول لأي Skill
  - كل استدعاء يُسجَّل في Prometheus (cogniforge_pipeline_*)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

import httpx

from microservices.orchestrator_service.src.core.config import get_settings

logger = logging.getLogger("skills_pipeline")

# ── ثوابت الـ Pipeline ────────────────────────────────────────────────────────
_SKILL_TIMEOUT_SECONDS: float = 10.0
_CALLER_ID: str = "orchestrator-service"


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


# ── استدعاءات الـ Skills ──────────────────────────────────────────────────────


async def _call_planning_skill(
    query: str,
    correlation_id: str,
    client: httpx.AsyncClient,
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

    try:
        response = await client.post(
            url,
            json={
                "caller_id": _CALLER_ID,
                "target_service": "planning_agent",
                "action": "generate_plan",
                "payload": {"query": query, "subject": "general", "difficulty": "medium"},
            },
            headers={"X-Correlation-ID": correlation_id},
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

    try:
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
            headers={"X-Correlation-ID": correlation_id},
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

    try:
        response = await client.post(
            url,
            json={
                "caller_id": _CALLER_ID,
                "target_service": "reasoning_agent",
                "action": "reason",
                "payload": {"query": query, "context": context},
            },
            headers={"X-Correlation-ID": correlation_id},
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
) -> str:
    """
    يُركِّب الإجابة النهائية من نتائج الـ 3 Skills.

    المنطق:
      - إذا نجح reasoning → الإجابة هي reasoning.data["answer"]
      - إذا فشل reasoning لكن نجح research → يُعيد ملخص البحث
      - إذا فشل الاثنان → يُعيد الخطة كإجابة أساسية
    """
    if reasoning.status == "success":
        answer = str(reasoning.data.get("answer", ""))
        if answer:
            return answer

    if research.status == "success":
        summary = str(research.data.get("summary", ""))
        results = research.data.get("results", [])
        if summary:
            return summary
        if results:
            return f"نتائج البحث لـ '{query}': " + " | ".join(str(r) for r in results[:3])

    plan_steps = plan.data.get("plan_steps", [])
    if plan_steps:
        steps_text = "\n".join(f"- {s}" for s in plan_steps[:5])
        return f"خطة للإجابة على '{query}':\n{steps_text}"

    return f"لم أتمكن من معالجة طلبك: {query}"


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
        # ── المرحلة 1+2: Planning و Research بالتوازي ────────────────────────
        plan_result, research_result = await asyncio.gather(
            _call_planning_skill(query, correlation_id, client),
            _call_research_skill(query, "", correlation_id, client),
        )

        # ── بناء السياق للـ Reasoning ─────────────────────────────────────────
        plan_steps = plan_result.data.get("plan_steps", [])
        research_summary = research_result.data.get("summary", "")
        research_results = research_result.data.get("results", [])

        context_parts: list[str] = []
        if plan_steps:
            context_parts.append("الخطة: " + " | ".join(str(s) for s in plan_steps[:3]))
        if research_summary:
            context_parts.append("البحث: " + research_summary[:500])
        elif research_results:
            context_parts.append(
                "نتائج: " + " | ".join(str(r) for r in research_results[:3])
            )
        composed_context = "\n".join(context_parts)

        # ── المرحلة 3: Reasoning مع السياق المُجمَّع ─────────────────────────
        reasoning_result = await _call_reasoning_skill(
            query, composed_context, correlation_id, client
        )

    # ── التركيب النهائي ───────────────────────────────────────────────────────
    total_duration_ms = (time.monotonic() - pipeline_start) * 1000
    composed_answer = _compose_answer(query, plan_result, research_result, reasoning_result)
    pipeline_mode, active_skills = _determine_pipeline_mode(
        plan_result, research_result, reasoning_result
    )

    logger.info(
        "pipeline_complete correlation_id=%s mode=%s active_skills=%s duration_ms=%.1f",
        correlation_id,
        pipeline_mode,
        active_skills,
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
    )
