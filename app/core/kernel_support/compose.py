"""شريحة التركيب (D-260 — تفكيك hotspot `app/kernel.py` — CodeScene X-Ray).

يفكّ combinators التركيب الوظيفي الثلاثة (`_apply_middleware` ·
`_mount_routers` · `_configure_static_files`) إلى دوالٍ نقيةٍ مستقلة —
التطبيق يتكوَّن بالتركيب لا بالترتيب الإمبراطوري، والقشرة تفوَّض فقط.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.app_blueprint import MiddlewareSpec, RouterSpec, StaticFilesSpec
from app.middleware.static_files_middleware import (
    StaticFilesConfig,
    setup_static_files_middleware,
)

logger = logging.getLogger(__name__)


def _apply_middleware(app: FastAPI, stack: list[MiddlewareSpec]) -> FastAPI:
    """
    Combinator: تطبيق قائمة الميدل وير على التطبيق.
    """
    # Starlette يطبق الميدل وير بنمط LIFO، لذا نعكس القائمة للحفاظ على ترتيب الإعلان FIFO.
    for mw_cls, mw_options in reversed(stack):
        app.add_middleware(mw_cls, **mw_options)
    return app


def _mount_routers(app: FastAPI, registry: list[RouterSpec]) -> FastAPI:
    """
    Combinator: ربط الموجهات بالتطبيق.
    """
    for router, prefix in registry:
        app.include_router(router, prefix=prefix)
    return app


def _configure_static_files(app: FastAPI, spec: StaticFilesSpec) -> FastAPI:
    """يضبط خدمة الملفات الثابتة بشكل صريح مع احترام وضع API-only."""
    if spec.enabled:
        static_config = StaticFilesConfig(
            enabled=True,
            serve_spa=spec.serve_spa,
        )
        setup_static_files_middleware(app, static_config)
    else:
        logger.info("🚀 Running in API-only mode (no static files)")
    return app
