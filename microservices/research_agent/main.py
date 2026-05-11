"""
وكيل البحث (Research Agent) — الخطوة 7.

هذه الخدمة مسؤولة عن استرجاع المعلومات (Retrieval)، وإعادة الترتيب (Reranking)،
وإدارة المحتوى (Content Management) من مصادر المعرفة المختلفة.
تُضيف الخطوة 7: /metrics endpoint حقيقي بصيغة Prometheus + Tavily web search حي.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from microservices.research_agent import prom_metrics
from microservices.research_agent.src.content.service import content_service
from microservices.research_agent.src.search_engine.models import SearchFilters, SearchRequest
from microservices.research_agent.src.search_engine.orchestrator import search_orchestrator
from microservices.research_agent.src.search_engine.super_search import SuperSearchOrchestrator

# Singleton: lazy-initialised on first deep_research call to avoid import-time
# credential errors when OPENAI_API_KEY / OPENROUTER_API_KEY is absent.
_super_search_orchestrator: SuperSearchOrchestrator | None = None


def _get_super_search() -> SuperSearchOrchestrator:
    """يُعيد SuperSearchOrchestrator مُهيَّأً بشكل كسول (lazy singleton)."""
    global _super_search_orchestrator
    if _super_search_orchestrator is None:
        _super_search_orchestrator = SuperSearchOrchestrator()
    return _super_search_orchestrator


# ── تحديد توفر Tavily ────────────────────────────────────────────────────────
_TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
_TAVILY_AVAILABLE = bool(_TAVILY_API_KEY)

try:
    from tavily import TavilyClient as _TavilyCheck  # noqa: F401

    _TAVILY_IMPORTABLE = True
except ImportError:
    _TAVILY_IMPORTABLE = False

_TAVILY_READY = _TAVILY_AVAILABLE and _TAVILY_IMPORTABLE


@asynccontextmanager
async def lifespan(app: FastAPI):
    """يدير دورة حياة وكيل البحث — الخطوة 7."""
    # ── Phase 1: تسجيل معلومات الإقلاع ──────────────────────────────────────
    db_url = os.environ.get("RESEARCH_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    db_backend = "postgresql" if "postgresql" in db_url else "sqlite"
    tavily_str = "true" if _TAVILY_READY else "false"

    prom_metrics.set_startup_info(
        version="1.0.0",
        environment=os.environ.get("ENVIRONMENT", "development"),
        db_backend=db_backend,
        tavily_available=tavily_str,
    )

    print(f"🚀 Research Agent Started — Tavily={'✅' if _TAVILY_READY else '❌ (no key)'}")
    yield
    print("🛑 Research Agent Stopped")


# --- Unified Agent Protocol ---


class AgentRequest(BaseModel):
    """
    طلب تنفيذ إجراء موحد.
    """

    caller_id: str = Field(..., description="Entity requesting the action")
    target_service: str = Field("research_agent", description="Target service name")
    action: str = Field(..., description="Action to perform (e.g., 'search')")
    payload: dict[str, object] = Field(default_factory=dict, description="Action arguments")
    security_token: str | None = Field(None, description="Auth token")


class AgentResponse(BaseModel):
    """
    استجابة موحدة للوكيل.
    """

    status: str = Field(..., description="'success' or 'error'")
    data: object | None = Field(None, description="Result data")
    error: str | None = Field(None, description="Error message")
    metrics: dict[str, object] = Field(default_factory=dict, description="Performance metrics")


# ------------------------------


def _build_router() -> APIRouter:
    """بناء موجهات الخدمة."""
    router = APIRouter()

    @router.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        """فحص الحالة."""
        return {
            "status": "healthy",
            "service": "research-agent",
            "step": "7",
            "tavily_available": "true" if _TAVILY_READY else "false",
        }

    @router.get("/metrics", tags=["Observability"], include_in_schema=False)
    def prometheus_metrics() -> Response:
        """
        يُصدِّر مقاييس Prometheus بصيغة text format.
        يُستخدَم من قِبَل Prometheus scraper على :8007/metrics.
        """
        body, content_type = prom_metrics.export_prometheus_text()
        return Response(content=body, media_type=content_type)

    @router.get("/content/curriculum", tags=["Content"])
    async def get_curriculum(level: str | None = None) -> dict[str, object]:
        """Fetch curriculum structure."""
        return await content_service.get_curriculum_structure(level)

    @router.get("/content/{content_id}", tags=["Content"])
    async def get_content(content_id: str, include_solution: bool = False) -> dict[str, str]:
        """Fetch raw content markdown."""
        data = await content_service.get_content_raw(content_id, include_solution=include_solution)
        if not data:
            raise HTTPException(status_code=404, detail="Content not found")
        return data

    @router.get("/content/{content_id}/solution", tags=["Content"])
    async def get_solution(content_id: str) -> dict[str, str]:
        """Fetch solution markdown."""
        data = await content_service.get_content_raw(content_id, include_solution=True)
        if not data:
            raise HTTPException(status_code=404, detail="Content not found")
        if "solution" not in data:
            raise HTTPException(status_code=404, detail="Solution not found")
        return {"solution_md": data["solution"]}

    @router.post("/execute", response_model=AgentResponse, tags=["Agent"])
    async def execute(request: AgentRequest) -> AgentResponse:
        """
        نقطة الدخول الموحدة لتنفيذ الأوامر (Unified Execution Endpoint).
        """
        try:
            # Dispatch Logic
            if request.action in {"search", "retrieve", "deep_research"}:
                # Extract parameters
                query = request.payload.get("query", "")
                filters_dict = request.payload.get("filters")
                if not isinstance(filters_dict, dict):
                    filters_dict = {}
                limit = request.payload.get("limit")
                if not isinstance(limit, int):
                    limit = 5

                # Check if deep research is requested or implied
                is_deep = request.action == "deep_research" or request.payload.get(
                    "deep_dive", False
                )

                if is_deep:
                    # Use Super Search (Internet)
                    print(f"🚀 Using Deep Research for: {query}")
                    _t = prom_metrics.get_request_timer()
                    try:
                        report = await _get_super_search().execute(query)
                        prom_metrics.record_deep_research("success")
                        prom_metrics.record_search(
                            "deep", "success", prom_metrics.elapsed_since(_t)
                        )
                        if _TAVILY_READY:
                            prom_metrics.record_tavily_call("success")
                        # The client expects 'results' list, so we wrap the report as a single result
                        data_results = [
                            {
                                "content": report,
                                "source": "Internet Research",
                                "score": 1.0,
                                "title": f"Deep Research Report: {query}",
                                "snippet": report[:200],
                            }
                        ]
                    except Exception as e:
                        prom_metrics.record_deep_research("error")
                        prom_metrics.record_search("deep", "error", prom_metrics.elapsed_since(_t))
                        if _TAVILY_READY:
                            prom_metrics.record_tavily_error("api_error")
                        return AgentResponse(status="error", error=f"Deep research failed: {e}")
                else:
                    # Construct SearchRequest for DB Search
                    try:
                        search_filters = SearchFilters(**filters_dict)
                    except Exception as e:
                        return AgentResponse(status="error", error=f"Invalid filters: {e}")

                    search_req = SearchRequest(q=query, filters=search_filters, limit=limit)

                    # Execute Search via Orchestrator
                    _t = prom_metrics.get_request_timer()
                    try:
                        results = await search_orchestrator.search(search_req)
                        prom_metrics.record_search("db", "success", prom_metrics.elapsed_since(_t))
                    except Exception as e:
                        prom_metrics.record_search("db", "error", prom_metrics.elapsed_since(_t))
                        return AgentResponse(status="error", error=f"Search failed: {e}")

                    # Serialize results
                    data_results = [r.model_dump() for r in results]

                return AgentResponse(
                    status="success",
                    data={"results": data_results, "total": len(data_results)},
                    metrics={"retrieval_ms": 0},  # Orchestrator metrics to be added
                )

            if request.action == "refine":
                query = request.payload.get("query")
                api_key = request.payload.get("api_key") or os.environ.get("OPENROUTER_API_KEY")

                if not isinstance(query, str) or not query:
                    return AgentResponse(status="error", error="Missing query for refinement.")
                if not isinstance(api_key, str) or not api_key:
                    return AgentResponse(status="error", error="Missing API key for refinement.")

                from microservices.research_agent.src.search_engine.query_refiner import (
                    get_refined_query,
                )

                # Use asyncio.to_thread to prevent blocking the event loop
                refined = await asyncio.to_thread(get_refined_query, query, api_key)
                return AgentResponse(status="success", data=refined, metrics={})

            if request.action == "rerank":
                query = request.payload.get("query", "")
                documents = request.payload.get("documents", [])
                top_n = request.payload.get("top_n", 5)

                if not query or not documents:
                    return AgentResponse(
                        status="error", error="Missing query or documents for reranking."
                    )

                from microservices.research_agent.src.search_engine.reranker import (
                    get_reranker,
                )

                reranker = get_reranker()
                # Run rerank in thread pool
                reranked = await asyncio.to_thread(reranker.rerank, query, documents, top_n)
                return AgentResponse(status="success", data=reranked, metrics={})

            if request.action == "retrieve_knowledge_graph":
                query = request.payload.get("query")
                limit = request.payload.get("limit", 5)
                if not isinstance(limit, int):
                    limit = 5

                if not isinstance(query, str) or not query:
                    return AgentResponse(status="error", error="Missing query for retrieval.")

                from microservices.research_agent.src.search_engine.llama_retriever import (
                    KnowledgeGraphRetriever,
                )

                retriever = KnowledgeGraphRetriever(top_k=limit)
                nodes = await retriever.aretrieve(query)

                # Serialize nodes
                data_results = []
                for node_with_score in nodes:
                    # node_with_score is NodeWithScore object
                    # We need to extract data manually as it might not be Pydantic serializable directly
                    node = node_with_score.node
                    data_results.append(
                        {
                            "text": node.text,
                            "metadata": node.metadata,
                            "score": node_with_score.score,
                        }
                    )

                return AgentResponse(status="success", data=data_results, metrics={})

            return AgentResponse(
                status="error", error=f"Action '{request.action}' not supported by Research Agent."
            )

        except Exception as e:
            return AgentResponse(status="error", error=str(e))

    return router


def create_app() -> FastAPI:
    """إنشاء تطبيق FastAPI لوكيل البحث."""
    app = FastAPI(
        title="Research Agent",
        description="خدمة مخصصة للبحث واسترجاع المعلومات (Microservice)",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.include_router(_build_router())
    return app


app = create_app()
