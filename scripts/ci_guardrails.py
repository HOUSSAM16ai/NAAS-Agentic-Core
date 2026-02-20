"""ماسح معماري قائم على AST للتحقق من الالتزام بالحدود."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ANY_TOKEN = "A" + "ny"

FORBIDDEN_PATTERNS = [
    {
        "pattern": "create_async_engine",
        "allowed_in": ["app/core/database.py", "migrations/env.py", "scripts/*", "tests/*"],
        "message": "Direct use of 'create_async_engine' is forbidden. Use the shared factory in app.core.database.",
    },
    {
        "pattern": "async_sessionmaker",
        "allowed_in": ["app/core/database.py", "scripts/*", "tests/*"],
        "message": "Direct use of 'async_sessionmaker' is forbidden. Use the shared factory in app.core.database.",
    },
    {
        "pattern": "create_engine",
        "allowed_in": ["app/core/database.py", "migrations/env.py", "scripts/*", "tests/*"],
        "message": "Direct use of 'create_engine' is forbidden. Use the shared factory in app.core.database.",
    },
    {
        "pattern": "sessionmaker",
        "allowed_in": ["app/core/database.py", "scripts/*", "tests/*"],
        "message": "Direct use of 'sessionmaker' is forbidden. Use the shared factory in app.core.database.",
    },
    {
        "pattern": "print",
        "allowed_in": ["scripts/*", "cli.py", "tests/*", "examples/*", "dev_setup.py"],
        "message": "Use of 'print()' is forbidden in application code. Use 'app.core.logging' instead.",
    },
]

FORBIDDEN_ATTRIBUTE_CALLS = [
    {
        "pattern": "create_all",
        "allowed_in": ["migrations/*", "scripts/*", "tests/*"],
        "message": "Schema auto-creation via 'create_all' is forbidden outside migrations/tests.",
    },
]

LEGACY_EXEMPTIONS = {
    "app/core/gateway/policy.py": [ANY_TOKEN],
    "app/core/gateway/service.py": [ANY_TOKEN],
    "app/core/gateway/cache.py": [ANY_TOKEN],
    "app/core/gateway/providers/anthropic.py": [ANY_TOKEN],
    "app/core/gateway/providers/base.py": [ANY_TOKEN],
    "app/core/gateway/providers/openai.py": [ANY_TOKEN],
    "app/core/gateway/protocols/grpc.py": [ANY_TOKEN],
    "app/core/gateway/protocols/rest.py": [ANY_TOKEN],
    "app/core/gateway/protocols/graphql.py": [ANY_TOKEN],
    "app/core/gateway/protocols/base.py": [ANY_TOKEN],
    "app/core/gateway/protocols/cache.py": [ANY_TOKEN],
    "app/core/gateway/strategies/implementations.py": [ANY_TOKEN],
    "app/core/domain/models.py": [ANY_TOKEN],
    "app/core/resilience/circuit_breaker.py": [ANY_TOKEN],
    "app/core/resilience/composite.py": [ANY_TOKEN],
    "app/core/resilience/bulkhead.py": [ANY_TOKEN],
    "app/core/ai_config.py": ["print"],
    "app/core/event_bus_impl.py": ["print"],
    "app/tooling/repository_map.py": ["print"],
    "app/api/routers/security.py": ["db_import"],
    "app/api/routers/customer_chat.py": ["db_import"],
    "app/api/routers/admin.py": ["db_import"],
    "app/api/routers/ums.py": ["db_import"],
    "app/api/routers/system/__init__.py": [ANY_TOKEN],
    "app/monitoring/metrics.py": [ANY_TOKEN],
    "app/monitoring/dashboard.py": [ANY_TOKEN],
    "app/monitoring/performance.py": [ANY_TOKEN],
    "app/monitoring/alerts.py": [ANY_TOKEN],
    "app/monitoring/exporters.py": [ANY_TOKEN],
    "app/middleware/core/hooks.py": ["print"],
    "app/middleware/observability/analytics_adapter.py": ["print"],
    "app/middleware/observability/telemetry_bridge.py": ["print"],
    "app/services/overmind/code_intelligence/*": ["print"],
    "app/services/system/horizontal_scaling_service.py": ["print"],
    "app/services/admin/chat_persistence.py": ["db_import"],
    "app/services/admin/chat_streamer.py": ["db_import"],
    "infra/pipelines/data_quality_checkpoint.py": [ANY_TOKEN],
    "microservices/orchestrator_service/database.py": [
        "create_async_engine",
        "create_all",
        "sessionmaker",
    ],
    "microservices/planning_agent/database.py": [
        "create_async_engine",
        "create_all",
        "sessionmaker",
    ],
    "microservices/memory_agent/database.py": ["create_async_engine", "create_all", "sessionmaker"],
    "microservices/user_service/database.py": ["create_all"],
    "app/cli_handlers/db_cli.py": ["create_all"],
    "scripts/verify_admin_flow.py": ["create_all"],
    "app/api/routers/content.py": ["db_import"],
    "app/api/routers/missions/router.py": ["db_import"],
    "scripts/verify_settings_standalone.py": ["monolith_import"],
    "microservices/**": [ANY_TOKEN],
    "app/**": [ANY_TOKEN],
    "yaml/**": [ANY_TOKEN],
}


def check_file(filepath: Path) -> list[str]:
    """يفحص ملف بايثون واحد بحثًا عن انتهاكات الحواجز المعمارية."""
    errors: list[str] = []
    exemptions = _get_exemptions_for_path(filepath)

    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(filepath))
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"Error parsing {filepath}: {exc}", file=sys.stderr)
        return errors

    parts = filepath.parts

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            _check_forbidden_calls(node, filepath, exemptions, errors)
        if isinstance(node, ast.Attribute):
            _check_forbidden_attribute_access(node, filepath, exemptions, errors)

    if "microservices" in parts and "tests" not in parts:
        _check_microservice_isolation(tree, filepath, errors, exemptions)

    if "app" in parts and "core" not in parts and "tests" not in parts:
        _check_monolith_isolation(tree, filepath, errors, exemptions)

    if _match_path(filepath, "app/api/routers/*") or _match_path(filepath, "app/services/admin/*"):
        _check_admin_db_imports(tree, filepath, errors, exemptions)

    if "tests" not in parts and "scripts" not in parts and ANY_TOKEN not in exemptions:
        _check_any_usage(tree, filepath, errors)

    return errors


def run_guardrails(root_dir: Path) -> list[str]:
    """يجمع الانتهاكات عبر المستودع بالكامل."""
    violations: list[str] = []

    for root, _, files in os.walk(root_dir):
        for filename in files:
            if not filename.endswith(".py"):
                continue
            filepath = Path(root) / filename
            if any(
                part in filepath.parts
                for part in [".venv", "venv", ".git", "__pycache__", "node_modules"]
            ):
                continue
            if "migrations" in filepath.parts or "migrations_archive" in filepath.parts:
                continue
            violations.extend(check_file(filepath))

    return violations


def main() -> int:
    """ينفذ ماسح الحواجز ويعيد رمز الخروج المناسب."""
    print("🛡️  Running Architecture Guardrails...")
    violations = run_guardrails(REPO_ROOT)

    if violations:
        print("\n❌ Guardrails violations found:")
        for violation in violations:
            print(violation)
        return 1

    print("\n✅ Guardrails passed.")
    return 0


def _normalize_path(filepath: Path) -> str:
    """يعيد المسار بصيغة نسبية موحدة لتطابق الاستثناءات."""
    try:
        relative_path = filepath.relative_to(REPO_ROOT)
        return relative_path.as_posix()
    except ValueError:
        return filepath.as_posix()


def _match_path(filepath: Path, pattern: str) -> bool:
    """يطابق المسارات باستخدام نمط glob بسيط."""
    from fnmatch import fnmatch

    normalized_path = _normalize_path(filepath)
    if fnmatch(normalized_path, pattern):
        return True
    return fnmatch(filepath.as_posix(), f"*{pattern}")


def _get_exemptions_for_path(filepath: Path) -> list[str]:
    """يعيد قائمة الاستثناءات المطبقة على المسار باستخدام أنماط glob."""
    if not _is_repo_path(filepath):
        return []
    matched_exemptions: set[str] = set()
    for pattern, exemptions in LEGACY_EXEMPTIONS.items():
        if _match_path(filepath, pattern):
            matched_exemptions.update(exemptions)
    return sorted(matched_exemptions)


def _is_repo_path(filepath: Path) -> bool:
    """يتحقق مما إذا كان المسار ضمن جذر المستودع."""
    try:
        filepath.relative_to(REPO_ROOT)
    except ValueError:
        return False
    return True


def _check_forbidden_calls(
    node: ast.Call,
    filepath: Path,
    exemptions: list[str],
    errors: list[str],
) -> None:
    if ANY_TOKEN in exemptions:
        return

    func_name = node.func.id
    for check in FORBIDDEN_PATTERNS:
        if func_name != check["pattern"]:
            continue
        if check["pattern"] in exemptions:
            return
        allowed = any(
            _match_path(filepath, allowed_pattern) for allowed_pattern in check["allowed_in"]
        )
        if not allowed:
            errors.append(f"{filepath}:{node.lineno} - {check['message']}")


def _check_forbidden_attribute_access(
    node: ast.Attribute,
    filepath: Path,
    exemptions: list[str],
    errors: list[str],
) -> None:
    """يفحص استخدام الخصائص المحظورة مثل create_all خارج المسارات المسموحة."""
    if ANY_TOKEN in exemptions:
        return

    attr_name = node.attr
    for check in FORBIDDEN_ATTRIBUTE_CALLS:
        if attr_name != check["pattern"]:
            continue
        if check["pattern"] in exemptions:
            return
        allowed = any(
            _match_path(filepath, allowed_pattern) for allowed_pattern in check["allowed_in"]
        )
        if not allowed:
            errors.append(f"{filepath}:{node.lineno} - {check['message']}")


def _check_microservice_isolation(
    tree: ast.AST,
    filepath: Path,
    errors: list[str],
    exemptions: list[str],
) -> None:
    parts = filepath.parts
    try:
        ms_index = parts.index("microservices")
    except ValueError:
        return

    if ms_index + 1 >= len(parts):
        return

    current_service = parts[ms_index + 1]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _check_microservice_imports(node, current_service, filepath, errors, exemptions)


def _check_monolith_isolation(
    tree: ast.AST, filepath: Path, errors: list[str], exemptions: list[str]
) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _check_monolith_imports(node, filepath, errors, exemptions)


def _check_admin_db_imports(
    tree: ast.AST,
    filepath: Path,
    errors: list[str],
    exemptions: list[str],
) -> None:
    if "db_import" in exemptions:
        return

    forbidden_db = ["sqlalchemy", "sqlmodel", "alembic", "app.core.database"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = _get_modules_from_import(node)
            for module_name in modules:
                for db_mod in forbidden_db:
                    if module_name.startswith(db_mod) or module_name == db_mod:
                        errors.append(
                            f"{filepath}:{node.lineno} - UI/API Layer cannot import DB module '{module_name}'. Use Services/Boundaries."
                        )


def _check_any_usage(tree: ast.AST, filepath: Path, errors: list[str]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == ANY_TOKEN:
            errors.append(
                f"{filepath}:{node.lineno} - Use of '{ANY_TOKEN}' is forbidden. Use specific types or 'object'."
            )
        elif isinstance(node, ast.Attribute) and node.attr == ANY_TOKEN:
            errors.append(f"{filepath}:{node.lineno} - Use of '{ANY_TOKEN}' is forbidden.")


def _get_modules_from_import(node: ast.Import | ast.ImportFrom) -> list[str]:
    modules: list[str] = []
    if isinstance(node, ast.Import):
        for name in node.names:
            modules.append(name.name)
    elif isinstance(node, ast.ImportFrom) and node.module:
        modules.append(node.module)
    return modules


def _check_microservice_imports(
    node: ast.Import | ast.ImportFrom,
    current_service: str,
    filepath: Path,
    errors: list[str],
    exemptions: list[str],
) -> None:
    if ANY_TOKEN in exemptions or "microservice_import" in exemptions:
        return

    modules = _get_modules_from_import(node)

    for module_name in modules:
        if module_name == "microservices" or module_name.startswith("microservices."):
            parts = module_name.split(".")
            if len(parts) == 1:
                errors.append(
                    f"{filepath}:{node.lineno} - Direct import of 'microservices' package is forbidden."
                )
                continue
            imported_service = parts[1]
            if imported_service != current_service:
                errors.append(
                    f"{filepath}:{node.lineno} - Cross-service import forbidden: '{current_service}' importing from '{imported_service}'"
                )

        if module_name.startswith("app.services"):
            errors.append(
                f"{filepath}:{node.lineno} - Microservice cannot import 'app.services' (Monolith Leak)."
            )

        if module_name.startswith("app.api"):
            errors.append(
                f"{filepath}:{node.lineno} - Microservice cannot import 'app.api' (Layer Violation)."
            )

        if module_name.startswith("app.") and not module_name.startswith("app.core"):
            errors.append(
                f"{filepath}:{node.lineno} - Microservice can only import from 'app.core'. Found: '{module_name}'"
            )


def _check_monolith_imports(
    node: ast.Import | ast.ImportFrom,
    filepath: Path,
    errors: list[str],
    exemptions: list[str],
) -> None:
    if ANY_TOKEN in exemptions or "monolith_import" in exemptions:
        return

    modules = _get_modules_from_import(node)
    for module_name in modules:
        if module_name == "microservices" or module_name.startswith("microservices."):
            errors.append(
                f"{filepath}:{node.lineno} - Monolith cannot import 'microservices' directly. Use APIs."
            )


if __name__ == "__main__":
    raise SystemExit(main())
