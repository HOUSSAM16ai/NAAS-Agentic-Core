"""مساعدات بناء خريطة قاعدة البيانات لمعرفة Overmind."""

from collections.abc import Iterable


def build_database_map(
    tables: Iterable[tuple[str, dict[str, object], int]],
) -> dict[str, object]:
    """يبني خريطة كاملة لقاعدة البيانات من معلومات الجداول."""
    tables_list = list(tables)
    database_map: dict[str, object] = {
        "total_tables": len(tables_list),
        "tables": {},
        "relationships": [],
    }

    tables_section: dict[str, object] = {}
    relationships: list[dict[str, object]] = []

    for table_name, schema, count in tables_list:
        tables_section[table_name] = {
            "schema": schema,
            "row_count": count,
        }

        for fk in _iter_foreign_keys(schema):
            relationships.append(
                {
                    "from_table": table_name,
                    "from_column": fk["column"],
                    "to_table": fk["references_table"],
                    "to_column": fk["references_column"],
                }
            )

    database_map["tables"] = tables_section
    database_map["relationships"] = relationships
    return database_map


def _iter_foreign_keys(schema: dict[str, object]) -> list[dict[str, object]]:
    """يحاول استخراج المفاتيح الأجنبية من بنية الجدول بأمان."""
    foreign_keys = schema.get("foreign_keys", [])
    if isinstance(foreign_keys, list):
        return [item for item in foreign_keys if isinstance(item, dict)]
    return []
