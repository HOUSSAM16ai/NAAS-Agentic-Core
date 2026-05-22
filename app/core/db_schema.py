"""مدقق مخطط قاعدة البيانات.

يتولى التحقق من المخطط وإصلاحه تلقائيًا عند بدء التشغيل مع احترام
مبدأ المسؤولية الواحدة ودعم تعدد محركات قواعد البيانات.
"""

import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.agents.system_principles import format_architecture_system_principles
from app.core.database import engine
from app.core.db_schema_config import _ALLOWED_TABLES, REQUIRED_SCHEMA, SchemaValidationResult

logger = logging.getLogger(__name__)

_SQLITE_SKIP_INDEX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bUSING\s+hnsw\b", flags=re.IGNORECASE),
    re.compile(r"\bUSING\s+GIN\b", flags=re.IGNORECASE),
)

__all__ = ["validate_schema_on_startup"]


def _to_sqlite_ddl(sql: str) -> str:
    """يحوّل أوامر PostgreSQL إلى صيغة متوافقة مع SQLite."""
    sql = re.sub(
        r"SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT", sql, flags=re.IGNORECASE
    )
    sql = re.sub(r"TIMESTAMPTZ", "TIMESTAMP", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bJSON\b", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bJSONB\b", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"vector\(\d+\)", "TEXT", sql, flags=re.IGNORECASE)
    # SQLite يرفض دوال DEFAULT غير الثابتة؛ نُسقط gen_random_uuid() قبل تحويل UUID→TEXT.
    sql = re.sub(r"DEFAULT\s+gen_random_uuid\(\)", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bUUID\b", "TEXT", sql, flags=re.IGNORECASE)

    if _should_skip_sqlite_index(sql):
        return ""

    sql = re.sub(r"tsvector GENERATED ALWAYS AS .*? STORED", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\btsvector\b", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"DEFAULT TRUE", "DEFAULT 1", sql, flags=re.IGNORECASE)
    sql = re.sub(r"DEFAULT FALSE", "DEFAULT 0", sql, flags=re.IGNORECASE)
    sql = re.sub(r"NOW\(\)", "CURRENT_TIMESTAMP", sql, flags=re.IGNORECASE)
    return re.sub(r"ADD COLUMN IF NOT EXISTS", "ADD COLUMN", sql, flags=re.IGNORECASE)


def _apply_dialect_ddl(conn: AsyncConnection, sql: str) -> str:
    """يوائم أوامر DDL حسب محرك قاعدة البيانات النشط."""
    return _to_sqlite_ddl(sql) if conn.dialect.name == "sqlite" else sql


def _should_skip_sqlite_index(sql: str) -> bool:
    """يتحقق مما إذا كان الأمر يحتوي على فهرس غير مدعوم في SQLite."""
    return any(pattern.search(sql) for pattern in _SQLITE_SKIP_INDEX_PATTERNS)


def _assert_schema_whitelist_alignment() -> None:
    """يتأكد من تطابق المخطط مع قائمة الجداول المسموح بها."""
    defined_tables = set(REQUIRED_SCHEMA.keys())
    undefined_tables = defined_tables - _ALLOWED_TABLES
    missing_definitions = _ALLOWED_TABLES - defined_tables

    if undefined_tables:
        raise ValueError(f"Unauthorized table in schema: {', '.join(sorted(undefined_tables))}")

    if missing_definitions:
        raise ValueError(
            f"Missing schema definition for allowed tables: {', '.join(sorted(missing_definitions))}"
        )


_assert_schema_whitelist_alignment()


async def _get_existing_columns(conn: AsyncConnection, table_name: str) -> set[str]:
    """يجلب أعمدة الجدول الحالية من قاعدة البيانات."""
    dialect_name = conn.dialect.name

    if dialect_name == "sqlite":
        result = await conn.execute(
            text("SELECT * FROM pragma_table_info(:table_name)"),
            {"table_name": table_name},
        )
        return {row[1] for row in result.fetchall()}

    result = await conn.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name = :table_name"),
        {"table_name": table_name},
    )
    return {row[0] for row in result.fetchall()}


async def _table_exists(conn: AsyncConnection, table_name: str) -> bool:
    """يتحقق من وجود الجدول في قاعدة البيانات."""
    dialect_name = conn.dialect.name

    if dialect_name == "sqlite":
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"),
            {"table_name": table_name},
        )
        return result.fetchone() is not None

    result = await conn.execute(
        text(
            "SELECT EXISTS ("
            "SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :table_name"
            ")"
        ),
        {"table_name": table_name},
    )
    return bool(result.scalar())


async def _fix_missing_column(
    conn: AsyncConnection,
    table_name: str,
    col: str,
    auto_fix_queries: dict[str, str],
    index_queries: dict[str, str],
) -> bool:
    """يحاول إصلاح العمود الناقص وإضافة الفهرس المرتبط به إن لزم."""
    if col not in auto_fix_queries:
        return False

    query = _apply_dialect_ddl(conn, auto_fix_queries[col])

    try:
        await conn.execute(text(query))
        logger.info(f"✅ Added missing column: {table_name}.{col}")

        if col in index_queries:
            idx_query = _apply_dialect_ddl(conn, index_queries[col])
            await conn.execute(text(idx_query))
            logger.info(f"✅ Created index for: {table_name}.{col}")

        return True
    except Exception as exc:
        logger.error(f"❌ Failed to fix {table_name}.{col}: {exc}")
        return False


def _infer_index_name(index_query: str) -> str | None:
    """يستنتج اسم الفهرس من عبارة SQL."""
    pattern = re.compile(r"INDEX(?: IF NOT EXISTS)?\s+\"([^\"]+)\"", flags=re.IGNORECASE)
    match = pattern.search(index_query)
    if match:
        return match.group(1)
    return None


async def _get_existing_indexes(conn: AsyncConnection, table_name: str) -> set[str]:
    """يجلب أسماء الفهارس الحالية من قاعدة البيانات."""
    dialect_name = conn.dialect.name

    if dialect_name == "sqlite":
        result = await conn.execute(
            text("SELECT name FROM pragma_index_list(:table_name)"),
            {"table_name": table_name},
        )
        return {row[0] for row in result.fetchall()}

    result = await conn.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename = :table_name"),
        {"table_name": table_name},
    )
    return {row[0] for row in result.fetchall()}


async def _ensure_missing_indexes(
    conn: AsyncConnection,
    table_name: str,
    index_queries: dict[str, str],
    index_names: dict[str, str],
    existing_columns: set[str],
    auto_fix: bool,
) -> tuple[list[str], list[str], list[str]]:
    """يتأكد من وجود الفهارس المطلوبة مع تسجيل ما تم إنشاؤه أو فقده."""
    missing_indexes: list[str] = []
    fixed_indexes: list[str] = []
    errors: list[str] = []

    try:
        existing_indexes = await _get_existing_indexes(conn, table_name)
    except Exception as exc:
        return missing_indexes, fixed_indexes, [f"Error reading indexes for {table_name}: {exc}"]

    for key, index_query in index_queries.items():
        index_name = index_names.get(key) or _infer_index_name(index_query)

        if not index_name:
            errors.append(f"Unable to infer index name for {table_name}.{key}")
            continue

        if index_name in existing_indexes:
            continue

        if not auto_fix:
            missing_indexes.append(f"{table_name}.{index_name}")
            continue

        if key not in existing_columns:
            errors.append(
                f"Cannot create index {index_name} on {table_name} because column {key} is missing"
            )
            missing_indexes.append(f"{table_name}.{index_name}")
            continue

        try:
            await conn.execute(text(_apply_dialect_ddl(conn, index_query)))
            fixed_indexes.append(f"{table_name}.{index_name}")
            logger.info(f"✅ Created missing index: {table_name}.{index_name}")
        except Exception as exc:
            errors.append(f"Failed to create index {table_name}.{index_name}: {exc}")
            missing_indexes.append(f"{table_name}.{index_name}")

    return missing_indexes, fixed_indexes, errors


async def validate_and_fix_schema(auto_fix: bool = True) -> SchemaValidationResult:
    """يتحقق من مخطط قاعدة البيانات ويصلح النواقص حسب السياسة المحددة."""
    results: SchemaValidationResult = {
        "status": "ok",
        "checked_tables": [],
        "missing_columns": [],
        "fixed_columns": [],
        "missing_indexes": [],
        "fixed_indexes": [],
        "errors": [],
    }

    try:
        async with engine.connect() as conn:
            for table_name, schema_info in REQUIRED_SCHEMA.items():
                if table_name not in _ALLOWED_TABLES:
                    continue

                results["checked_tables"].append(table_name)

                table_exists = await _table_exists(conn, table_name)

                if not table_exists:
                    create_query = schema_info.get("create_table")

                    if create_query and auto_fix:
                        try:
                            await conn.execute(text(_apply_dialect_ddl(conn, create_query)))
                            logger.info(f"✅ Created missing table: {table_name}")
                            existing_columns = set(schema_info.get("columns", []))
                            results["fixed_columns"].extend(
                                [f"{table_name}.{col}" for col in existing_columns]
                            )
                            table_exists = True
                        except Exception as exc:
                            results["errors"].append(f"Failed to create table {table_name}: {exc}")
                            continue
                    else:
                        results["errors"].append(
                            f"Table {table_name} is missing and cannot be auto-created"
                        )
                        continue

                try:
                    existing_columns = await _get_existing_columns(conn, table_name)
                except Exception as exc:
                    results["errors"].append(f"Error checking table {table_name}: {exc}")
                    continue

                required_columns = set(schema_info.get("columns", []))
                missing = required_columns - existing_columns

                if missing:
                    results["missing_columns"].extend([f"{table_name}.{col}" for col in missing])

                    if auto_fix:
                        auto_fix_queries = schema_info.get("auto_fix", {})
                        index_queries = schema_info.get("indexes", {})

                        for col in missing:
                            if await _fix_missing_column(
                                conn, table_name, col, auto_fix_queries, index_queries
                            ):
                                results["fixed_columns"].append(f"{table_name}.{col}")

                index_queries = schema_info.get("indexes", {})
                index_names = schema_info.get("index_names", {})

                if index_queries:
                    missing_idx, fixed_idx, index_errors = await _ensure_missing_indexes(
                        conn=conn,
                        table_name=table_name,
                        index_queries=index_queries,
                        index_names=index_names,
                        existing_columns=existing_columns,
                        auto_fix=auto_fix,
                    )

                    results["missing_indexes"].extend(missing_idx)
                    results["fixed_indexes"].extend(fixed_idx)
                    results["errors"].extend(index_errors)

            if results["fixed_columns"] or results["fixed_indexes"]:
                await conn.commit()

    except Exception as exc:
        results["status"] = "error"
        results["errors"].append(f"Schema validation failed: {exc}")
        logger.error(f"❌ Schema validation error: {exc}")

    unresolved_columns = set(results["missing_columns"]) - set(results["fixed_columns"])
    unresolved_indexes = set(results["missing_indexes"]) - set(results["fixed_indexes"])

    if results["errors"]:
        results["status"] = "error"
    elif unresolved_columns or unresolved_indexes:
        results["status"] = "warning"

    return results


async def validate_schema_on_startup() -> None:
    """ينفذ تحقق بدء التشغيل ويعرض النتائج في السجل."""
    logger.info("🔍 Validating database schema... (جاري فحص مخطط قاعدة البيانات)")
    logger.info(
        format_architecture_system_principles(
            header="مبادئ المعمارية وحوكمة البيانات (Validation Context):",
            bullet="-",
            include_header=True,
        )
    )

    results = await validate_and_fix_schema(auto_fix=True)

    if results["status"] == "ok":
        logger.info("✅ Schema validation passed (المخطط سليم)")
    elif results["fixed_columns"] or results["fixed_indexes"]:
        logger.warning(
            "⚠️ Schema auto-fixed: "
            f"columns={results['fixed_columns']}, indexes={results['fixed_indexes']}"
        )
    elif results["missing_columns"] or results["missing_indexes"]:
        logger.error(
            "❌ CRITICAL: Missing schema elements: "
            f"columns={results['missing_columns']}, indexes={results['missing_indexes']}"
        )

    if results["errors"]:
        for error in results["errors"]:
            logger.error(f"   Error: {error}")
