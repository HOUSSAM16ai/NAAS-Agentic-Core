"""يتحقق من منع الاستيراد المباشر بين خدمات الميكروسيرفس للحفاظ على الاستقلالية."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MICROSERVICES_ROOT = REPO_ROOT / "microservices"


def _violations_for_file(path: Path, service_name: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=path.as_posix())
    violations: list[str] = []
    allowed_prefix = f"microservices.{service_name}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if not name.startswith("microservices."):
                    continue
                if not name.startswith(allowed_prefix):
                    violations.append(f"{path}:{node.lineno} import {name}")
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not module.startswith("microservices."):
                continue
            if not module.startswith(allowed_prefix):
                violations.append(f"{path}:{node.lineno} from {module} import ...")
    return violations


def main() -> int:
    violations: list[str] = []
    for service_dir in MICROSERVICES_ROOT.iterdir():
        if not service_dir.is_dir() or service_dir.name.startswith("__"):
            continue
        service_name = service_dir.name
        for py_file in service_dir.rglob("*.py"):
            if "tests" in py_file.parts:
                continue
            if py_file.name == "__init__.py":
                continue
            violations.extend(_violations_for_file(py_file, service_name))

    if violations:
        print("❌ Cross-service imports detected:")
        for item in violations:
            print(f" - {item}")
        return 1

    print("✅ No cross-service imports detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
