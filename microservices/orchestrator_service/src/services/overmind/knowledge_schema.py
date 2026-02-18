"""مساعدات بناء وتسجيل بنية قاعدة البيانات لمعرفة Overmind."""

from app.core.di import get_logger

logger = get_logger(__name__)

SchemaColumn = dict[str, object]
ForeignKey = dict[str, str]
TableSchema = dict[str, object]


def build_schema_object(
    table_name: str,
    columns: list[SchemaColumn],
    primary_keys: list[str],
    foreign_keys: list[ForeignKey],
) -> TableSchema:
    """يبني كائن البنية النهائي من مكونات الجدول."""
    return {
        "table_name": table_name,
        "columns": columns,
        "primary_keys": primary_keys,
        "foreign_keys": foreign_keys,
        "total_columns": len(columns),
    }


def log_schema_info(
    table_name: str,
    columns: list[SchemaColumn],
    primary_keys: list[str],
    foreign_keys: list[ForeignKey],
) -> None:
    """يسجل ملخصاً لمعلومات البنية المسترجعة."""
    logger.info(
        "Retrieved schema for '%s': %s columns, %s PKs, %s FKs",
        table_name,
        len(columns),
        len(primary_keys),
        len(foreign_keys),
    )
