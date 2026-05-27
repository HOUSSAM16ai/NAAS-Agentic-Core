"""
مساعدات إعدادات CogniForge.

يوفر هذا الملف توابع نقية وخفيفة لتطبيع القيم البيئية
وتحسين مسارات الإعدادات دون الاعتماد على مكتبات ثقيلة.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import pathlib
import secrets

logger = logging.getLogger("app.core.settings")

_DEV_SECRET_KEY_CACHE: str | None = None


def _resolve_state_key_path() -> pathlib.Path:
    """يكتشف مسار ملف المفتاح الثابت آلياً حسب موقع التطبيق.

    ISS-091 (D-SECRET-002): الإصدار السابق ثبَّت ``/app/.devcontainer/state``
    وهو يعمل فقط داخل devcontainer رسمي (WORKDIR=/app). خارجه (Codespaces
    fork، Gitpod workspace=/workspaces/<repo>، تنفيذ يدوي من /home/user/...)
    لا يوجد ``/app`` فينحدر الكود إلى توليد مفتاح في الذاكرة فقط — وهذا هو
    السبب الجذري المتبقي لـ "kick → re-enter" بعد ISS-090.

    أولوية الحل:
      1. ``DEV_SECRET_KEY_FILE`` env (override صريح للعمليات).
      2. ``/app/.devcontainer/state/dev_secret_key`` (devcontainer رسمي).
      3. ``<file>/../../../.devcontainer/state/dev_secret_key`` (نفس الـ repo
         بغض النظر عن الـ CWD — يعمل في كل البيئات).
    """
    explicit = os.environ.get("DEV_SECRET_KEY_FILE", "").strip()
    if explicit:
        return pathlib.Path(explicit)

    canonical = pathlib.Path("/app/.devcontainer/state/dev_secret_key")
    if canonical.parent.exists() or pathlib.Path("/app").exists():
        return canonical

    # موقع المستودع المُستنتج من ملف helpers.py نفسه:
    # app/core/settings/helpers.py → repo root هو parents[3].
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    return repo_root / ".devcontainer" / "state" / "dev_secret_key"


def _get_or_create_dev_secret_key() -> str:
    """يُعيد مفتاحاً ثابتاً للتطوير محفوظاً على القرص.

    يمنع إبطال جلسات المستخدمين عند إعادة تشغيل uvicorn.
    الأولوية: SECRET_KEY في process env → ملف على القرص → إنشاء جديد وحفظه.
    """
    global _DEV_SECRET_KEY_CACHE

    # 1. إذا كان في process env مباشرة → استخدمه (يشمل ما يُحقنه supervisor.sh)
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key and env_key not in ("dev-secret-change-me", "changeme"):
        _DEV_SECRET_KEY_CACHE = env_key
        return env_key

    # 2. cache في الذاكرة (نفس process)
    if _DEV_SECRET_KEY_CACHE is not None:
        return _DEV_SECRET_KEY_CACHE

    # 3. ملف ثابت على القرص (يبقى عبر restarts) — مسار يُكتشف ديناميكياً
    try:
        key_path = _resolve_state_key_path()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if key_path.exists():
            stored = key_path.read_text().strip()
            if len(stored) >= 32:
                _DEV_SECRET_KEY_CACHE = stored
                logger.info(
                    "dev_secret_key loaded from disk path=%s len=%d",
                    key_path,
                    len(stored),
                )
                return stored
        # إنشاء مفتاح جديد وحفظه
        new_key = secrets.token_urlsafe(64)
        key_path.write_text(new_key)
        # نضبط الصلاحيات على 600 لمنع قراءة المفتاح من قِبل مستخدمين آخرين
        with contextlib.suppress(OSError):
            key_path.chmod(0o600)
        _DEV_SECRET_KEY_CACHE = new_key
        logger.warning(
            "dev_secret_key GENERATED + saved to disk path=%s — "
            "first boot or state file was missing",
            key_path,
        )
        return new_key
    except Exception as exc:
        logger.error(
            "dev_secret_key disk persistence failed (%s) — using in-memory key. "
            "JWTs will be invalidated on every restart!",
            exc,
        )
        # fallback آمن إذا فشل القرص — هذا هو السبب الجذري لـ "kick → re-enter"
        # إذا وصل التنفيذ هنا، تعقَّب الخطأ في os env DEV_SECRET_KEY_FILE.
        if _DEV_SECRET_KEY_CACHE is None:
            _DEV_SECRET_KEY_CACHE = secrets.token_urlsafe(64)
        return _DEV_SECRET_KEY_CACHE


def _ensure_database_url(value: str | None, environment: str) -> str:
    """يضمن وجود رابط قاعدة بيانات صالح مع بدائل آمنة للبيئات غير الإنتاجية."""
    if value:
        return value

    if environment == "production":
        raise ValueError("❌ CRITICAL: DATABASE_URL is missing in PRODUCTION!")

    if environment == "testing":
        return "sqlite+aiosqlite:///:memory:"

    raise ValueError(
        "❌ CRITICAL: DATABASE_URL is missing! You must configure the database connection explicitly."
    )


def _upgrade_postgres_protocol(url: str) -> str:
    """يرفع بروتوكولات قواعد البيانات إلى نسخ Async متوافقة مع asyncpg."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and "aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def _normalize_postgres_ssl(url: str) -> str:
    """يوحد معاملات SSL في روابط PostgreSQL إلى صيغة واحدة آمنة."""
    if not url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
        return url

    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    if not parsed.query:
        return url

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    sslmode_value: str | None = None
    filtered_items: list[tuple[str, str]] = []
    for key, value in query_items:
        if key == "sslmode":
            sslmode_value = value
            continue
        if key == "ssl":
            continue
        filtered_items.append((key, value))

    if sslmode_value is not None:
        filtered_items.append(("ssl", sslmode_value))

    new_query = urlencode(filtered_items, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _normalize_csv_or_list(value: list[str] | str | None) -> list[str]:
    """يطبع قيَم CSV أو JSON إلى قائمة نصية مرتبة دون تكرار."""
    if value is None:
        return []

    def _deduplicate(items: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                normalized.append(item)
        return normalized

    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return _deduplicate(cleaned)

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return []

        if candidate.startswith("[") and candidate.endswith("]"):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    cleaned = [str(item).strip() for item in parsed if str(item).strip()]
                    return _deduplicate(cleaned)
            except json.JSONDecodeError:
                pass

        cleaned = [item.strip() for item in candidate.split(",") if item.strip()]
        return _deduplicate(cleaned)

    return []


def _is_valid_email(value: str) -> bool:
    """يتحقق من تنسيق بريد إلكتروني بسيط وآمن للاستخدام الإداري."""
    candidate = value.strip().lower()
    if not candidate or " " in candidate:
        return False
    if candidate.count("@") != 1:
        return False
    local, _, domain = candidate.partition("@")
    if not local or not domain:
        return False
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    if "." not in domain or domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return False
    return len(domain.split(".")[-1]) >= 2


def _lenient_json_loads(value: str) -> object:
    """يفسر قيم البيئة كـ JSON مع السماح بالنصوص عند فشل التحليل."""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
