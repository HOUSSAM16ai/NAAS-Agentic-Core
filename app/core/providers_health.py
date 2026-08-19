"""
فحص حالة المزودين الحيّ (LLM / بحث) عند الإقلاع — D-245 (2026-08-13).

**المشكلة التي يعالجها:** كان النظام يبدأ بصمتٍ تام حتى حين تكون كل مفاتيح
المزودين مفقودة (GitHub Codespaces بلا أسرار)، فيترجم المستخدم كل سؤال إلى
«النظام لا يجيب» دون سببٍ مُعلَن — بينما الكود الداخلي كان يعرف السبب
(`_check_provider_config` في strategy_handlers) لكنه لا يفصح عنه إلا عند
أول سؤالٍ فاشل.

**القانون الدائم (D-245):** ⛔ لا إقلاعٌ بلا إعلانٍ صريحٍ لحالة كل مزوّدٍ
حرج (قاعدة البيانات · LLM · البحث)؛ فمن ولد بلا معرفةِ ما ينقصه سيموت
باسمٍ خاطئ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from shared.ambient_memory import AmbientMemoryConfig


def _utc_iso() -> str:
    """الوقت الحالي UTC بصيغة ISO مختصرة (ثوانٍ)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class ProvidersHealthState:
    """حالة المزودين الحرجين — تُقرأ من أيّ نقطة صحة بلا تكلفة."""

    llm_provider: str = "unknown"  # "configured" | "missing"
    llm_detail: str = ""
    search_provider: str = "unknown"  # "configured" | "fallback"
    search_detail: str = ""
    orchestrator: str = "unknown"  # "reachable" | "unreachable" (D-112 + D-245)
    orchestrator_detail: str = ""
    # D-269: طبقة الهوية المعرفية المحيطة. الحالات من `ProbeState` — قائمة مغلقة،
    # و`not_configured` **ليست** عطلاً: الطبقة اختيارية ولا تمسّ دور الطالب.
    ambient_memory: str = "unknown"
    ambient_memory_detail: str = ""
    checked_at: str = field(default_factory=_utc_iso)

    def summarize(self) -> dict[str, object]:
        return {
            "llm": {"status": self.llm_provider, "detail": self.llm_detail},
            "search": {"status": self.search_provider, "detail": self.search_detail},
            "orchestrator": {
                "status": self.orchestrator,
                "detail": self.orchestrator_detail,
            },
            # الساق الثالثة من البرهان الثلاثي (§6.6): وجودُ مفتاحٍ ليس قدرة،
            # ودليلُ التشغيل يُعرَض هنا كي يُسأل عنه لا كي يُفترَض.
            "ambient_memory": {
                "status": self.ambient_memory,
                "detail": self.ambient_memory_detail,
            },
            "checked_at": self.checked_at,
        }


async def check_orchestrator_reachable() -> None:
    """
    D-112 + D-245 (2026-08-13): العمود الفقري الإلزامي — الإجابات لا تأتي إلا
    من الـ orchestrator microservice. عند تعذّر الاتصال به يجب أن يُعلَن ذلك
    في /health قبل أول سؤالٍ مرفوضٍ بـ ORCHESTRATOR_REQUIRED — لا «النظام لا
    يجيب» بلا سببٍ معلَن.
    """
    import asyncio

    from app.core.settings.base import get_settings

    try:
        url = get_settings().ORCHESTRATOR_SERVICE_URL
        async with asyncio.timeout(5):
            from shared.http_client import (
                correlated_client,  # D-189: outgoing probes go through the correlated client (X-Correlation-ID), never a raw AsyncClient
            )

            async with correlated_client(timeout=5.0) as client:
                resp = await client.get(f"{url}/health")
        if resp.status_code < 500:
            _STATE.orchestrator = "reachable"
            _STATE.orchestrator_detail = f"{url} responds (HTTP {resp.status_code})"
        else:
            _STATE.orchestrator = "unreachable"
            _STATE.orchestrator_detail = f"{url} → HTTP {resp.status_code}"
    except Exception as exc:
        _STATE.orchestrator = "unreachable"
        _STATE.orchestrator_detail = f"live probe failed: {type(exc).__name__}" + (
            f": {exc}" if str(exc) else ""
        )


def ambient_memory_config() -> AmbientMemoryConfig:
    """يبني إعداد الطبقة من القارئ القانوني — `shared/` لا يقرأ البيئة بنفسه (D-189)."""
    from app.core.settings.base import get_settings

    settings = get_settings()
    return AmbientMemoryConfig(
        api_key=settings.HONCHO_API_KEY,
        base_url=settings.HONCHO_BASE_URL,
        api_version=settings.HONCHO_API_VERSION,
        workspace_id=settings.HONCHO_WORKSPACE_ID,
        timeout_seconds=settings.HONCHO_PROBE_TIMEOUT_SECONDS,
    )


async def check_ambient_memory_reachable() -> None:
    """D-269: مسبارٌ حيٌّ للطبقة الخامسة — استعلامُ قراءةٍ فقط.

    ⛔ لا يُرسَل أيّ نصّ محادثةٍ ولا مُعرَّف طالب: النداء الوحيد يسأل «هل تقبلني؟».
    وفشلُه يُعلَن ولا يُرفَع — طرفٌ ثالثٌ لا يُسقط إقلاع المنصّة (نمط D-074).
    """
    from shared.ambient_memory import probe_ambient_memory

    try:
        result = await probe_ambient_memory(ambient_memory_config())
    except Exception as exc:
        _STATE.ambient_memory = "unreachable"
        _STATE.ambient_memory_detail = f"مسبارٌ فشل بشكلٍ غير متوقَّع ({type(exc).__name__})."
        return
    _STATE.ambient_memory = result.state
    _STATE.ambient_memory_detail = result.detail


_STATE = ProvidersHealthState()


def probe_providers_health() -> ProvidersHealthState:
    """
    فحصٌ إعلانيٌّ للمزودين الحرجين. لا رميٌ للأخطاء — إعلانٌ فقط:
    النظام يجب أن يعرف ما ينقصه قبل أول سؤالٍ فاشل.
    """
    from app.core.settings.base import get_settings

    settings = get_settings()
    if settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY:
        state = "configured"
        detail = "OPENROUTER_API_KEY set" if settings.OPENROUTER_API_KEY else "OPENAI_API_KEY set"
    else:
        state = "missing"
        detail = (
            "لا OPENROUTER_API_KEY ولا OPENAI_API_KEY — النظام لن يجيب على الأسئلة "
            "(🛑 خطأ التكوين المُبلَّغ عنه في strategy_handlers عند أول سؤال)"
        )
    _STATE.llm_provider = state
    _STATE.llm_detail = detail

    # D-268 (ISS-191): القراءة عبر القارئ القانوني لا `os.environ` (CLAUDE.md §6).
    if settings.TAVILY_API_KEY or settings.FIRECRAWL_API_KEY:
        _STATE.search_provider = "configured"
        _STATE.search_detail = "TAVILY/FIRECRAWL key set"
    else:
        _STATE.search_provider = "fallback"
        _STATE.search_detail = "DuckDuckGo fallback only — slower, rate-limited"

    _STATE.checked_at = _utc_iso()
    return _STATE


def get_providers_health_state() -> ProvidersHealthState:
    """الحالة المعلنة للمزودين — قراءة بلا تكلفة."""
    return _STATE
