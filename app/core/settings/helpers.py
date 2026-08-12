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


def _sync_db_url() -> str | None:
    """يعيد DATABASE_URL بصيغة psycopg متزامنة (postgresql:// عادية).

    ينزَّع `+asyncpg` إن وجدت — لا قراءة من unit database (تجنب circular
    import أثناء تهيئة Pydantic settings)."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


# ── (K-ROOT) مفتاح سري ثابت عبر البيئات العابرة — Codespaces / replit ──────
# الجذر الحقيقي لتقرير "login failed عند دخول Codespace جديدة بنفس الحساب":
# كان المفتاح يُولَّد عشوائياً ويُحفظ في `.devcontainer/state/dev_secret_key` —
# وهذا المسار **يُمسح مع بيئة Codespace المحذوفة**، فتتولد بيئةٌ جديدة بمفتاحٍ
# جديد، وتُرفض كل JWTs السابقة (401) وتُعطل تدوير refresh token عبر البيئات.
# الحل: طبقة دائمة واحدة عبر كل البيئات — قاعدة البيانات (Supabase) نفسها.
# المنطق الآن:
#   1. SECRET_KEY في process env (التزام صريح من المشغِّل)              ✓
#   2. قرص محلي (يبقى عبر restarts داخل البيئة نفسها)                  ✓
#   3. **المفتاح المخزَّن في `app_state` بجدول دائم في DB** ← جديد       ✓
#   4. توليد جديد + حفظه في DB + قرص معًا (مفتاحٌ واحد دائم عبر البيئات) ✓
#
# هذا يعني: Codespace محذوفة أو جديدة أو معاد بناؤها تستعيد **نفس المفتاح**
# الذي وقَّع جلسات المستخدمين، فلا يظهر "login failed" مجدداً.


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


def _read_state_from_db(key: str) -> str | None:
    """قراءة قيمة `app_state` عبر psycopg متزامن مباشر (لا AsyncEngine pool).

    ⛔ `engine.pool.connect()` يرفع `MissingGreenlet` لأن pool asyncpg غير
    قابل للاستخدام من سياق متزامن — فنفتح اتصال psycopg قصيراً من نفس
    DATABASE_URL دون أي اعتماد على unit database (تجنب circular import
    أثناء تهيئة Pydantic settings).
    """
    try:
        _psql_url = _sync_db_url()
        if not _psql_url:
            return None
        import psycopg

        with psycopg.connect(_psql_url, autocommit=True) as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = %(k)s",
                {"k": key},
            ).fetchone()
            if row and isinstance(row[0], str) and len(row[0]) >= 32:
                logger.info("dev_secret_key restored from app_state (DB)")
                return row[0]
        return None
    except Exception as exc:
        logger.debug("dev_secret_key DB restore failed (%s)", exc)
        return None


def _get_or_create_dev_secret_key() -> str:
    """يُعيد مفتاحاً ثابتاً عبر كل البيئات — env → القرص → DB → توليد جديد.

    انظر أعلى هذا الملف (K-ROOT) لفلسفة الطبقات الأربع.
    """
    global _DEV_SECRET_KEY_CACHE

    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key and env_key not in ("dev-secret-change-me", "changeme"):
        _DEV_SECRET_KEY_CACHE = env_key
        return env_key

    if _DEV_SECRET_KEY_CACHE is not None:
        return _DEV_SECRET_KEY_CACHE

    # 3. قرص محلي (يبقى عبر restarts داخل البيئة نفسها).
    disk_key = _try_disk()
    if disk_key:
        _DEV_SECRET_KEY_CACHE = disk_key
        # مزامنة مع الطبقة الدائمة (في حال كانت الأولى في هذه البيئة)
        _persist_to_database(disk_key)
        return disk_key

    db_key = _try_database()
    if db_key:
        _DEV_SECRET_KEY_CACHE = db_key
        _persist_to_disk(db_key)
        return db_key

    # لم يوجد مفتاح سابق في أي طبقة — أول إقلاع مطلق: توليد + حفظ في الطبقتين.
    new_key = secrets.token_urlsafe(64)
    _DEV_SECRET_KEY_CACHE = new_key
    _persist_to_disk(new_key)
    _persist_to_database(new_key)
    logger.warning(
        "dev_secret_key GENERATED (first absolute boot) — persisted to disk + DB "
        "so every future Codespace/instance shares the SAME key",
    )
    return new_key


def _persist_to_disk(new_key: str) -> None:
    """يحفظ المفتاح على القرص بعد ضبط الصلاحيات على 600."""
    try:
        key_path = _resolve_state_key_path()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(new_key)
        with contextlib.suppress(OSError):
            key_path.chmod(0o600)
    except Exception as exc:
        logger.debug("dev_secret_key disk persist failed (%s)", exc)


def _try_disk() -> str | None:
    """يقرأ المفتاح من القرص المحلي إن وُجد."""
    try:
        key_path = _resolve_state_key_path()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if key_path.exists():
            stored = key_path.read_text().strip()
            if len(stored) >= 32:
                logger.info(
                    "dev_secret_key loaded from disk path=%s len=%d",
                    key_path,
                    len(stored),
                )
                return stored
        return None
    except Exception as exc:
        logger.debug("dev_secret_key disk read failed (%s)", exc)
        return None


def _try_database() -> str | None:
    """(K-ROOT) يقرأ المفتاح من `app_state` في DB — الطبقة الدائمة عبر البيئات."""
    return _read_state_from_db("dev_secret_key")


def _persist_to_database(new_key: str) -> None:
    """يحفظ المفتاح في `app_state` (Upsert عبر INSERT ON CONFLICT DO UPDATE).

    هذه هي الطبقة الدائمة الوحيدة عبر بيئات Codespaces المحذوفة.
    فشلها غير قاتل (يُحذَّر ويُحفظ فقط على القرص)، لكن نجاحها يمنع
    توليد مفتاح جديد في كل Codespace جديدة — أي منع "login failed" الدائم.

    ⛔ استيراد `app.core.database.engine` هنا يُطلق import مبكّرًا أثناء
    تهيئة Pydantic settings (قبل اكتمال وحدة database) فيفشل بح circular
    import. لذلك نلتقي المحرّك من خلال `get_db_engine()` المتأخر — وهو نفس
    المحرّك الذي يستخدمه كل التطبيق، دون أي import مباشر للموديول.
    """
    try:
        # psycopg 3 متزامن مباشر من DATABASE_URL —AsyncEngine pool يرفع
        # `MissingGreenlet` من سياق متزامن، فلا نستخدم `engine.pool.connect()`.
        _psql_url = _sync_db_url()
        if not _psql_url:
            logger.debug("dev_secret_key: no DATABASE_URL — persist skipped")
            return

        # إنشاء الجدول إن لم يكن موجوداً (أول إقلاع على DB نظيفة)
        _create_stmt = """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """
        _upsert_stmt = """
            INSERT INTO app_state (key, value, updated_at)
            VALUES (%(k)s, %(v)s, now())
            ON CONFLICT (key)
            DO UPDATE SET value = %(v)s, updated_at = now()
        """
        with contextlib.suppress(Exception):
            import psycopg

            with psycopg.connect(_psql_url, autocommit=True) as conn:
                conn.execute(_create_stmt)
                conn.execute(
                    _upsert_stmt,
                    {"k": "dev_secret_key", "v": new_key},
                )
            logger.info("dev_secret_key persisted to app_state (DB)")
    except Exception as exc:
        logger.error(
            "dev_secret_key DB persistence failed (%s) — key lives on disk only, "
            "sessions WILL be invalidated in new Codespaces!",
            exc,
        )


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
