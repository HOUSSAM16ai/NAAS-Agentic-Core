"""شريحة OTel (D-260 — تفكيك hotspot `app/kernel.py` — CodeScene X-Ray).

يفكّ استدعاءَي OpenTelemetry في `_construct_app` (step 0: SDK bootstrap قبل
تغليف FastAPI حتى يرى FastAPIInstrumentor التطبيق عند البناء · step 5:
per-app instrumentation حتى تقع spans في Tempo) إلى دالتين fail-soft
نقيتين — لا تتحمّل النواة أي تبعيةٍ مباشرة على otel_setup.

كلاهما hard no-op عند غياب OTEL_EXPORTER_OTLP_ENDPOINT — لا شيء يتغير
لـ Codespaces الافتراضي.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _bootstrap_otel_sdk(service_name: str | None) -> None:
    """step 0: OTel SDK bootstrap — قبل تغليف FastAPI (D-260).

    يُستدعى قبل `FastAPI()` حتى يرى FastAPIInstrumentor التطبيق عند البناء.
    Hard no-op عندما تكون OTEL_EXPORTER_OTLP_ENDPOINT غير مضبوطة.
    """
    try:
        from app.telemetry.otel_setup import setup_otel

        setup_otel(service_name=service_name or "cogniforge-monolith")
    except Exception:
        logger.debug("otel_setup invocation failed at kernel boot", exc_info=True)


def _instrument_app(app: object) -> None:
    """step 5: per-app instrumentation — يغلف كل route/middleware (D-260).

    No-op عندما لم يُهيَّأ OTel في الخطوة 0 — spans تقع في Tempo عند توافره.
    """
    try:
        from app.telemetry.otel_setup import instrument_fastapi_app

        instrument_fastapi_app(app)
    except Exception:
        logger.debug("instrument_fastapi_app invocation failed", exc_info=True)
