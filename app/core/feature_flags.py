"""
Feature flags — قارئ موحَّد لأعلام المسار التعليمي الحيّ (D-158).

قبل D-158 كان `_semantic_tutor_enabled()` مُعرَّفاً مرّتين بافتراضين متعارضين عند الاستثناء:
`customer_chat` يُرجِع True (يُحمِّل/يكتب `tutor_state`) و `orchestrator_client` يُرجِع False
(فتُعطَّل سلطة `DialogueManagerSkill`). هذا الملف هو المصدر الوحيد للقراءة: افتراض واحد لكل علم،
env أولاً ثم الإعدادات (12-factor)، fail-open.

- `semantic_tutor_enabled()`  — افتراض **True**: تحميل/كتابة ذاكرة جلسة التدريس الدائمة.
- `cognitive_turn_enabled()`   — افتراض **True** (D-159 — قرار المالك بعد نجاح التحقق الحي
  الكامل E2E: uvicorn + WS + الدخول الحقيقي + آلة الحالات A→B فوق `kc_progress` الدائم).
  الرجوع الفوري بلا deploy: `COGNITIVE_TURN_ENABLED=0`.

يعيش في `app.core` (لا `microservices/`) فيستورده كلٌّ من الـ routers و `infrastructure` دون
كسر حدود المعمارية (`check_no_app_imports` يستهدف `microservices/` فقط).
"""

from __future__ import annotations

import contextlib
import os

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _flag(env_name: str, settings_attr: str, default: bool) -> bool:
    """env أولاً ثم الإعدادات ثم الافتراض. fail-open إلى الافتراض عند أي تعذّر."""
    raw = os.getenv(env_name)
    if raw is not None:
        low = raw.strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
    with contextlib.suppress(Exception):
        from app.core.settings.base import get_settings

        value = getattr(get_settings(), settings_attr, None)
        if isinstance(value, bool):
            return value
    return default


def semantic_tutor_enabled() -> bool:
    """D-142/D-158: تحميل+كتابة `tutor_state` (ذاكرة جلسة التدريس). افتراض True."""
    return _flag("SEMANTIC_TUTOR_ENABLED", "SEMANTIC_TUTOR_ENABLED", True)


def cognitive_turn_enabled() -> bool:
    """D-158/D-159: طبقة القرار الموحَّدة `_cognitive_turn` فوق `tutor_state`.

    افتراض **True** منذ D-159 (بعد نجاح E2E الحي الكامل — قاعدة D-158-f استوفيت).
    الرجوع الفوري: `COGNITIVE_TURN_ENABLED=0` (env يتقدّم على الإعدادات، بلا deploy).
    """
    return _flag("COGNITIVE_TURN_ENABLED", "COGNITIVE_TURN_ENABLED", True)


__all__ = ["cognitive_turn_enabled", "semantic_tutor_enabled"]
