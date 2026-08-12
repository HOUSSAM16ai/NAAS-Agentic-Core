"""
طبقة قاعدة البيانات لـ orchestrator-service.

تُدير هذه الوحدة:
  1. AsyncEngine (SQLAlchemy + asyncpg) — للـ ORM والـ migrations
  2. AsyncPostgresSaver (LangGraph) — checkpointer دائم للـ StateGraph [Step 10]
  3. مقاييس Prometheus لكل عملية checkpointer

قواعد ISS-040 (PgBouncer):
  - SQLAlchemy engine: يستخدم statement_cache_size=0 لتوافق PgBouncer
  - AsyncPostgresSaver: يستخدم psycopg مباشرةً — يحتاج postgresql:// لا postgresql+asyncpg://
  - كلاهما يستخدم port 5432 (direct PG) لا 6543 (PgBouncer transaction mode)

قاعدة ISS-038-B (asyncpg URL):
  - create_async_engine يحتاج postgresql+asyncpg://
  - AsyncConnectionPool يحتاج postgresql:// (psycopg)
"""

from __future__ import annotations

import logging
import ssl
import time
from collections.abc import AsyncGenerator

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from microservices.orchestrator_service.src.core.config import settings
from microservices.orchestrator_service.src.models.mission import OrchestratorSQLModel

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ModuleNotFoundError:
    AsyncPostgresSaver = None  # type: ignore[assignment,misc]


# ── مقاييس Prometheus — استيراد دفاعي ────────────────────────────────────────
try:
    from microservices.orchestrator_service.src.core.prom_metrics import (
        record_checkpointer_error,
        record_checkpointer_read,
        record_checkpointer_write,
        set_checkpointer_active_threads,
        set_checkpointer_backend_info,
    )

    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False

    def record_checkpointer_write(*_: object, **__: object) -> None: ...
    def record_checkpointer_read(*_: object, **__: object) -> None: ...
    def record_checkpointer_error(*_: object, **__: object) -> None: ...
    def set_checkpointer_active_threads(*_: object, **__: object) -> None: ...
    def set_checkpointer_backend_info(*_: object, **__: object) -> None: ...


# ── Checkpointer wrapper مع مقاييس Prometheus ────────────────────────────────
# يرث من AsyncPostgresSaver مباشرةً لأن LangGraph يتحقق من isinstance(BaseCheckpointSaver).
# نُنشئ الـ class بشكل مشروط لتجنب NameError عند غياب langgraph-checkpoint-postgres.


def _make_instrumented_class(base_class: type) -> type:
    """
    يُنشئ _InstrumentedCheckpointer كـ subclass من base_class (AsyncPostgresSaver).

    هذا النهج يضمن أن LangGraph يقبل الـ checkpointer (isinstance check)
    بينما نُضيف مقاييس Prometheus على كل عملية.

    مبدأ "Instrumentation before visualization": كل عملية checkpoint
    مرئية في Grafana قبل أي dashboard.
    """

    class _InstrumentedCheckpointer(base_class):  # type: ignore[valid-type]
        """
        AsyncPostgresSaver مُعزَّز بمقاييس Prometheus.

        يرث كل سلوك AsyncPostgresSaver ويُضيف تسجيل Prometheus
        على aput / aget / aget_tuple / setup.

        D-174 (2026-08-12): LangGraph 0.2.x يدرج input/blob بـ version=None
        في checkpoint_blobs → NotNullViolation يسقط كل محادثة ("Response ended
        prematurely"). نحمي ذلك هنا (لا نغيّر pkg vendor).
        """

        UPSERT_CHECKPOINT_BLOBS_SQL = """
            INSERT INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type, blob)
            VALUES (%s, %s, %s, COALESCE(NULLIF(%s, ''), '0'), %s, %s)
            ON CONFLICT (thread_id, checkpoint_ns, channel, version) DO NOTHING
        """

        def _dump_blobs(self, thread_id, checkpoint_ns, values, versions):  # type: ignore[override]
            rows = super()._dump_blobs(thread_id, checkpoint_ns, values, versions)
            return [(t, ns, ch, ver if ver else "0", ty, bl) for (t, ns, ch, ver, ty, bl) in rows]

        def __init__(self, pool: object) -> None:
            super().__init__(pool)  # type: ignore[arg-type]
            # مجموعة thread_ids النشطة — تُستخدم لـ cogniforge_checkpointer_active_threads
            self._active_threads: set[str] = set()

        async def aput(  # type: ignore[override]
            self,
            config: dict[str, object],
            checkpoint: object,
            metadata: object,
            new_versions: object,
        ) -> object:
            """يكتب checkpoint مع تسجيل Prometheus."""
            thread_id: str = (
                config.get("configurable", {}).get("thread_id", "unknown")  # type: ignore[union-attr]
                if isinstance(config.get("configurable"), dict)
                else "unknown"
            )
            prefix = thread_id.split(":", maxsplit=1)[0] if ":" in thread_id else thread_id[:8]
            t0 = time.monotonic()
            try:
                result = await super().aput(config, checkpoint, metadata, new_versions)
                duration = time.monotonic() - t0
                record_checkpointer_write(prefix, "success", duration)
                self._active_threads.add(thread_id)
                set_checkpointer_active_threads(len(self._active_threads))
                return result
            except Exception as exc:
                duration = time.monotonic() - t0
                record_checkpointer_write(prefix, "error", duration)
                error_type = type(exc).__name__.lower()
                if "connection" in error_type or "pool" in error_type:
                    record_checkpointer_error("connection_error")
                elif "serial" in error_type or "json" in error_type:
                    record_checkpointer_error("serialization_error")
                elif "timeout" in error_type:
                    record_checkpointer_error("timeout")
                else:
                    record_checkpointer_error("unknown")
                raise

        async def aget(self, config: dict[str, object]) -> object:  # type: ignore[override]
            """يقرأ checkpoint مع تسجيل Prometheus."""
            thread_id: str = (
                config.get("configurable", {}).get("thread_id", "unknown")  # type: ignore[union-attr]
                if isinstance(config.get("configurable"), dict)
                else "unknown"
            )
            prefix = thread_id.split(":", maxsplit=1)[0] if ":" in thread_id else thread_id[:8]
            t0 = time.monotonic()
            try:
                result = await super().aget(config)
                duration = time.monotonic() - t0
                status = "hit" if result is not None else "miss"
                record_checkpointer_read(prefix, status, duration)
                return result
            except Exception as exc:
                duration = time.monotonic() - t0
                record_checkpointer_read(prefix, "error", duration)
                error_type = type(exc).__name__.lower()
                record_checkpointer_error(
                    "connection_error" if "connection" in error_type else "unknown"
                )
                raise

        async def aget_tuple(self, config: dict[str, object]) -> object:  # type: ignore[override]
            """يقرأ checkpoint tuple مع تسجيل Prometheus."""
            thread_id: str = (
                config.get("configurable", {}).get("thread_id", "unknown")  # type: ignore[union-attr]
                if isinstance(config.get("configurable"), dict)
                else "unknown"
            )
            prefix = thread_id.split(":", maxsplit=1)[0] if ":" in thread_id else thread_id[:8]
            t0 = time.monotonic()
            try:
                result = await super().aget_tuple(config)
                duration = time.monotonic() - t0
                status = "hit" if result is not None else "miss"
                record_checkpointer_read(prefix, status, duration)
                return result
            except Exception:
                duration = time.monotonic() - t0
                record_checkpointer_read(prefix, "error", duration)
                record_checkpointer_error("unknown")
                raise

        async def setup(self) -> None:
            """يُهيِّئ جداول checkpoint مع تسجيل Prometheus."""
            t0 = time.monotonic()
            try:
                await super().setup()
                duration = time.monotonic() - t0
                logger.info("[CHECKPOINTER] setup() completed in %.3fs", duration)
            except Exception:
                record_checkpointer_error("setup_error")
                raise

    return _InstrumentedCheckpointer


# نُنشئ الـ class فقط إذا كان AsyncPostgresSaver متاحاً
if AsyncPostgresSaver is not None:
    _InstrumentedCheckpointer = _make_instrumented_class(AsyncPostgresSaver)
else:
    # Stub بسيط عند غياب langgraph-checkpoint-postgres
    class _InstrumentedCheckpointer:  # type: ignore[no-redef]
        def __init__(self, pool: object) -> None:
            self._active_threads: set[str] = set()


# ── SQLAlchemy Engine ─────────────────────────────────────────────────────────


def create_engine() -> AsyncEngine:
    """
    يُنشئ AsyncEngine مع دعم كامل لـ Supabase PgBouncer (transaction mode).

    PgBouncer في وضع transaction لا يدعم prepared statements.
    الحل: statement_cache_size=0 في connect_args.
    """
    db_url = settings.DATABASE_URL
    url_obj = make_url(db_url)

    # SQLite (dev/sandbox/tests): aiosqlite does NOT accept asyncpg connect_args
    # (statement_cache_size / prepared_statement_cache_size / ssl). Passing them
    # raises TypeError on first connect → init_db() degrades and no tables are
    # created. Build a clean aiosqlite engine instead so the orchestrator can run
    # end-to-end against a shared SQLite file when Postgres egress is blocked.
    if url_obj.get_backend_name() == "sqlite":
        return create_async_engine(
            db_url,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False},
        )

    # D-178 (2026-08-12): عُزل حياً على Supabase: SQLAlchemy + asyncpg لا يمكن أن
    # تعمل على pgbouncer transaction mode (port 6543) حتى مع
    # statement_cache_size=0 — dialect يستدعي prepare() صريحاً بكل الأحوال
    # (sqlalchemy/dialects/postgresql/asyncpg.py::_prepare). الـ backend server
    # connection يُعاد استخدامه عبر pooler فيبقى statement server-side موجوداً.
    # الحل: تعطيل engine وتمرير كل ORM عبر psycopg pool الموثوق (يعمل 100% مع
    # prepared_statement_cache_size=0).
    qs = dict(url_obj.query)
    ssl_mode = qs.pop("sslmode", None) or qs.pop("ssl", None)

    connect_kwargs: dict[str, object] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

    # D-177 (2026-08-12): عُزل حياً على Supabase pgbouncer (transaction mode, port
    # 6543): حتى مع statement_cache_size=0، dialect asyncpg في SQLAlchemy 2.0.25
    # يستخدم batch mode — يجهّز statement مرة ويعيد استخدامه لكل تنفيذ، فيرتطم
    # بـ DuplicatePreparedStatement لأن pgbouncer لا يحفظ prepared statements بين
    # المعاملات. use_batch_mode=False يجبر dialect على prepare جديد داخل كل
    # transaction (يُفقد عبر pooler بشكل طبيعي) — 6/6 INSERT ناجحة حياً.
    execution_kwargs: dict[str, object] = {"use_batch_mode": False}

    if ssl_mode in ("require", "verify-ca", "verify-full"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_kwargs["ssl"] = ctx

    clean_url = url_obj.set(query=qs).render_as_string(hide_password=False)

    return create_async_engine(
        clean_url,
        echo=False,
        future=True,
        connect_args=connect_kwargs,
        execution_options=execution_kwargs,
    )


# Singleton: lazy-initialised on first get_engine() call to avoid import-time
# connection errors when ORCHESTRATOR_DATABASE_URL is not yet in the environment.
_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """يُعيد AsyncEngine مُهيَّأً بشكل كسول (lazy singleton)."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


# backward-compat alias
engine = None  # type: ignore[assignment]

_session_factory: async_sessionmaker | None = None  # type: ignore[type-arg]


def _get_session_factory() -> async_sessionmaker:  # type: ignore[type-arg]
    """يُعيد async_sessionmaker مُهيَّأً بشكل كسول."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


class _LazySessionFactory:
    """Proxy يُحيل الاستدعاء إلى _get_session_factory() عند أول استخدام."""

    def __call__(self, *args: object, **kwargs: object) -> AsyncSession:
        return _get_session_factory()(*args, **kwargs)  # type: ignore[return-value]

    def __getattr__(self, name: str) -> object:
        return getattr(_get_session_factory(), name)


async_session_factory = _LazySessionFactory()


def _psycopg_session_factory_proxy():
    """يُعيد PsycopgSession جديد من psycopg pool — بديل async_session_factory()"""
    pool = get_psycopg_pool()
    if pool is None:
        raise RuntimeError("psycopg pool not available")
    return psycopg_session_factory(pool)


# ── Psycopg ORM Sessions (D-178: bypass SQLAlchemy on pgbouncer) ─────────────
# SQLAlchemy asyncpg dialect يستخدم prepare() صريحاً في كل استعلام — مستحيل على
# pgbouncer transaction mode. psycopg pool + prepared_statement_cache_size=0
# يعمل 100% حيوياً (checkpointer نفسه). نبني Session خفيفاً متوافقاً مع واجهة
# text() المستخدمة فعلياً في كل مكان.
import re as _re

_NAMED_PARAM = _re.compile(r":(?P<name>[A-Za-z_][A-Za-z0-9_]*)")


class _RowDict(dict):
    """dict مع attribute access حتى تبقى ``row.id``/``row.title`` صالحة (كما في AsyncSession)."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"row has no attribute {name!r}") from None


class PsycopgSession:
    """جلسة خفيفة فوق psycopg AsyncConnectionPool تحاكي API الأساسي لـ AsyncSession

    للاستعلامات النصية فقط: ``execute(text(...), params)`` مع
    ``fetchone()``/``fetchall()``/``scalar_one_or_none()`` و``commit()``/
    ``rollback()`` (no-op لأن pool يعمل autocommit=True)."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool
        self._conn = None

    async def __aenter__(self) -> PsycopgSession:
        self._conn = await self._pool.getconn()
        # D-189 (2026-08-12): نضبط صراحةً على كل connection (pooler يعيد توجيه
        # connections جديدة وقد لا تسري pool kwargs):
        await self._conn.set_autocommit(True)  # async connection: read-only property، نستخدم await
        # D-198 (2026-08-12): prepare_threshold=None — تعطيل كامل للـ prepared
        # statements (تصحيح جوهري: 0 تعني "جهّز من أول تنفيذ" أي عكس المطلوب).
        # pgbouncer transaction mode لا يحفظ server-side statements بين المعاملات
        # (DuplicatePreparedStatement) — التعطيل الكامل هو المتوافق رسمياً.
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._conn is not None:
            await self._pool.putconn(self._conn)
            self._conn = None

    @staticmethod
    def _quote_literal_static(v):
        """inline-safe literal quoting (pgbouncer-compatible: no placeholders allowed)."""
        return PsycopgSession._quote_literal(v)

    @staticmethod
    def _quote_literal(v):
        """D-188 (2026-08-12): pgbouncer transaction mode يرفض psycopg placeholders
        بالكامل (0 placeholders / DuplicatePreparedStatement). الحل: inline literal
        interpolation مع escaping آمن.
        ملاحظة: هذه ليست طبقة SQL injection محمية — المستخدم لا يتحكم في
        :name params؛ كلها من كود orchestrator الداخلي الثابت.
        """
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v).replace("\\", "\\\\").replace("'", "''")
        return f"'{s}'"

    @staticmethod
    def _to_positional(sql: str, params: dict | None):
        """يحول :name params إلى literal values inline (لا placeholders).
        يدعم أيضًاً params كـ sequence مع %s في SQL (نحوّلها inline كذلك)."""
        if params is None:
            return sql, None
        if isinstance(params, dict):
            mapping = dict(params)
            new_sql = _NAMED_PARAM.sub(
                lambda m: PsycopgSession._quote_literal(mapping.get(m.group("name"))), sql
            )
            return new_sql, None
        # sequence positional: كل %s يتحول إلى literal
        if "%s" in sql:
            it = iter(params)
            new_sql = sql.replace("%s", "__PSEUDO_PLACEHOLDER__")
            try:
                parts = []
                for token in new_sql.split("__PSEUDO_PLACEHOLDER__"):
                    parts.append(token)
                # إعادة البناء: نضيف literal قبل كل placeholder ماعدا آخر part
                out = []
                for i, token in enumerate(parts):
                    out.append(token)
                    if i < len(parts) - 1:
                        out.append(PsycopgSession._quote_literal(next(it)))
                new_sql = "".join(out)
            except StopIteration:
                pass  # params أقل من %s — نتركها
        else:
            new_sql = sql
        return new_sql, None

    async def execute(self, statement, params=None):
        """ينفذ استعلام text() ويعيد result proxy خفيفاً (rows في .rows)."""
        if self._conn is None:
            raise RuntimeError("PsycopgSession used outside context manager")
        sql = statement.text if hasattr(statement, "text") else str(statement)
        sql, params = self._to_positional(sql, params)
        logger.debug("[PsycopgSession] execute sql=%r params=%r", sql, params)
        try:
            # D-188: pgbouncer transaction mode يرفض psycopg placeholders
            # بالكامل — كل القيم الآن inline literals فلا نمرر params أبداً.
            # D-198 (2026-08-12): تعطيل الـ prepared statements التلقائية أصبح
            # على مستوى pool عبر prepare_threshold=None (pool kwargs) — وهو ما
            # يحمي أيضاً كل العمليات الداخلية لـ LangGraph عبر نفس pool.
            # unnamed statements عبر Bind/Execute protocol تعمل على الـ pooler
            # ولا تحتاج prepare=False هنا، لكن وجوده لم يضر (double insurance).
            result = await self._conn.execute(sql, prepare=False)
            try:
                raw = await result.fetchall() if result.description else []
                rows = [_RowDict(r) for r in raw]
            except Exception:
                rows = []
            return _PsycopgResult(rows)
        except Exception as _exc:
            logger.error(
                "[PsycopgSession] execute FAILED sql=%r params=%r: %s",
                sql,
                params,
                _exc,
            )
            raise

    async def commit(self) -> None:
        pass  # autocommit=True

    async def rollback(self) -> None:
        pass  # autocommit=True

    async def close(self) -> None:
        if self._conn is not None:
            await self._pool.putconn(self._conn)
            self._conn = None


# D-191 (2026-08-12): alias عام للاستخدام الآمن في inline SQL (pgbouncer: لا placeholders)
_pgsafe_lit = PsycopgSession._quote_literal_static


class _PsycopgResult:
    """proxy خفيف يحاكي Result.fetchall/fetchone/scalar_one_or_none."""

    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        row = self._rows[0] if self._rows else None
        if row is None:
            return None
        values = list(row.values()) if hasattr(row, "values") else list(row)
        return values[0] if values else None


def psycopg_session_factory(pool: AsyncConnectionPool) -> PsycopgSession:
    return PsycopgSession(pool)


async def get_psycopg_db() -> AsyncGenerator[PsycopgSession, None]:
    """Depends بديل لـ get_db يعمل فوق psycopg pool (يعمل على pgbouncer)."""
    pool = get_psycopg_pool()
    if pool is None:
        raise RuntimeError("psycopg pool not available — checkpointer backend missing")
    async with psycopg_session_factory(pool) as session:
        try:
            yield session
        except Exception as exc:
            logger.error("Database session error (psycopg): %s", exc)
            await session.rollback()
            raise
        finally:
            await session.close()


def get_psycopg_pool() -> AsyncConnectionPool | None:
    """يعيد psycopg pool النشط (المستخدم أصلاً في checkpointer)."""
    return _postgres_pool


# ── Postgres Checkpointer (Step 10) ──────────────────────────────────────────

_postgres_pool: AsyncConnectionPool | None = None
postgres_checkpointer: _InstrumentedCheckpointer | None = None

# عدد connections في pool — يُستخدم في مقاييس Prometheus
_POOL_SIZE: int = 5


def get_checkpointer() -> _InstrumentedCheckpointer | None:
    """يُعيد الـ checkpointer المُهيَّأ أو None إذا لم يكن متاحاً."""
    return postgres_checkpointer


def _build_psycopg_conninfo(database_url: str) -> str:
    """
    يُحوِّل DATABASE_URL إلى psycopg conninfo string.

    psycopg يحتاج postgresql:// (لا postgresql+asyncpg://).
    يُزيل sslmode من query string ويُضيف sslmode=require مباشرةً.
    """
    url_obj = make_url(database_url)
    qs = dict(url_obj.query)
    ssl_mode = qs.pop("sslmode", "require")

    scheme = "postgresql"
    clean_url = url_obj.set(drivername=scheme, query=qs).render_as_string(hide_password=False)

    sep = "&" if "?" in clean_url else "?"
    return f"{clean_url}{sep}sslmode={ssl_mode}"


async def get_db() -> AsyncGenerator:
    """يُعيد جلسة DB للاستخدام في FastAPI Depends.

    D-178: عند توفر psycopg pool (Supabase pgbouncer) نستخدمه بدل SQLAlchemy
    asyncpg engine — engine asyncpg لا يمكن أن يعمل على pooler transaction mode.
    كل الاستعلامات في orchestrator تستخدم text() مع named params، وPsycopgSession
    يدعمها بالكامل (يدخل dict_row rows بأسماء الأعمدة، فيظل ``row.title`` صالحاً)."""
    if _postgres_pool is not None:
        async with psycopg_session_factory(_postgres_pool) as session:
            try:
                yield session
            except Exception as exc:
                logger.error("Database session error (psycopg): %s", exc)
                await session.rollback()
                raise
            finally:
                await session.close()
    else:
        async with async_session_factory() as session:
            try:
                yield session
            except Exception as exc:
                logger.error("Database session error: %s", exc)
                await session.rollback()
                raise
            finally:
                await session.close()


async def init_db() -> None:
    """
    يُهيِّئ قاعدة البيانات والـ checkpointer.

    المراحل:
      1. إنشاء جداول SQLModel (ORM)
      2. إنشاء AsyncConnectionPool لـ psycopg
      3. تهيئة AsyncPostgresSaver وإنشاء جداول checkpoint
      4. تسجيل معلومات backend في Prometheus
    """
    global _postgres_pool, postgres_checkpointer

    # ── PHASE 1: SQLModel tables ──────────────────────────────────────────
    # غير حرج في بيئة التطوير — الـ sandbox يحجب Postgres egress (port 5432/6543).
    # الخدمة تبدأ في وضع DEGRADED إذا فشل الاتصال بقاعدة البيانات.
    try:
        async with get_engine().begin() as conn:
            await conn.run_sync(OrchestratorSQLModel.metadata.create_all)
        logger.info("[DB] SQLModel tables created/verified.")
    except Exception as exc:
        logger.warning(
            "[DB] SQLModel table creation failed (non-fatal in dev): %s — "
            "continuing to Postgres checkpointer init (SQLModel DDL bypassed).",
            exc,
        )
        if _METRICS_AVAILABLE:
            record_checkpointer_error("db_init_failed")

    # ── PHASE 2 & 3: Postgres Checkpointer ───────────────────────────────
    if AsyncPostgresSaver is None:
        logger.warning(
            "[CHECKPOINTER] langgraph-checkpoint-postgres not installed — "
            "falling back to MemorySaver."
        )
        set_checkpointer_backend_info(backend="none", step="10", pool_size=0, tables_ready=False)
        return

    # SQLite (dev/sandbox): there is no Postgres to point psycopg at. Building a
    # psycopg conninfo from a sqlite URL yields an unreachable target and blocks
    # ~30s on AsyncConnectionPool.open() before failing, then re-tries forever.
    # Skip it cleanly and let the graph use the MemorySaver singleton.
    if make_url(settings.DATABASE_URL).get_backend_name() == "sqlite":
        logger.info("[CHECKPOINTER] SQLite backend — skipping Postgres checkpointer (MemorySaver).")
        set_checkpointer_backend_info(backend="memory", step="10", pool_size=0, tables_ready=False)
        return

    try:
        conninfo = _build_psycopg_conninfo(settings.DATABASE_URL)
        # R0.2 (D-172): AsyncPostgresSaver.setup() runs CREATE INDEX CONCURRENTLY,
        # which cannot run inside a transaction block — so the pool MUST use
        # autocommit connections, or setup() fails and the `checkpoints` table is
        # never created (checkpointer degrades). row_factory=dict_row is required
        # by AsyncPostgresSaver's queries. This mirrors LangGraph's documented usage.
        # D-198 (2026-08-12): على Supabase pooler (pgbouncer transaction mode) كل
        # statement مع اسم (prepared) يفشل بـ DuplicatePreparedStatement. التعطيل
        # الكامل عبر prepare_threshold=None في pool kwargs هو الحل المتوافق رسمياً
        # — أثبت الاختبار الحي (graph invoke كامل + put_writes + continuation).
        _postgres_pool = AsyncConnectionPool(
            conninfo=conninfo,
            min_size=1,
            max_size=_POOL_SIZE,
            open=False,
            kwargs={
                "autocommit": True,
                "row_factory": dict_row,
                "prepare_threshold": None,
                # D-198 (2026-08-12): تعطيل كامل للـ prepared statements.
                # الاختبار الحي أثبت: prepare_threshold=None + AsyncPostgresSaver
                # يعمل 100% على pgbouncer 6543 (graph invoke كامل + put_writes
                # pipeline + same-thread checkpoint continuation).
            },
        )
        await _postgres_pool.open()
        logger.info("[CHECKPOINTER] psycopg pool opened (max_size=%d).", _POOL_SIZE)

        # تحقق من الاتصال
        async with _postgres_pool.connection() as conn:
            await conn.execute("SELECT 1")

        # أنشئ _InstrumentedCheckpointer (subclass من AsyncPostgresSaver)
        # يقبله LangGraph لأنه isinstance(BaseCheckpointSaver)
        postgres_checkpointer = _InstrumentedCheckpointer(_postgres_pool)
        await postgres_checkpointer.setup()
        logger.info("[CHECKPOINTER] AsyncPostgresSaver.setup() completed — tables ready.")

        # تحقق من الجداول
        async with _postgres_pool.connection() as conn:
            result = await conn.execute(
                "SELECT COUNT(*) FROM pg_tables "
                "WHERE schemaname='public' AND tablename LIKE 'checkpoint%'"
            )
            row = await result.fetchone()
            # D-198: pool kwargs تحتوي row_factory=dict_row → row dict وليس tuple
            tables_count = row["count"] if row else 0

        tables_ready = tables_count >= 3
        logger.info("[CHECKPOINTER] checkpoint tables found: %d", tables_count)

        set_checkpointer_backend_info(
            backend="postgres",
            step="10",
            pool_size=_POOL_SIZE,
            tables_ready=tables_ready,
        )

        # اختبار قراءة حقيقي
        test_config = {"configurable": {"thread_id": "step10_init_probe"}}
        checkpoint = await postgres_checkpointer.aget(test_config)
        logger.info(
            "[CHECKPOINTER] ACTIVE — backend=postgres step=10 tables=%d pool_size=%d probe_hit=%s",
            tables_count,
            _POOL_SIZE,
            checkpoint is not None,
        )

    except Exception as exc:
        import traceback as _tb

        logger.error(
            "[CHECKPOINTER] init failed (non-fatal): %s | type=%s | tb=%s",
            exc,
            type(exc).__name__,
            _tb.format_exc()[-800:],
        )
        record_checkpointer_error("connection_error")
        set_checkpointer_backend_info(backend="none", step="10", pool_size=0, tables_ready=False)

    logger.info("[DB] init_db() completed.")


async def close_db() -> None:
    """يُغلق pool الـ checkpointer عند shutdown."""
    global _postgres_pool
    if _postgres_pool is not None:
        try:
            await _postgres_pool.close()
            logger.info("[CHECKPOINTER] psycopg pool closed.")
        except Exception as exc:
            logger.warning("[CHECKPOINTER] pool close error: %s", exc)
        _postgres_pool = None
