"""
مساعدات بناء بنية المشروع لمعرفة Overmind - النسخة الخارقة.

هذا الملف يوفر معرفة شاملة ودقيقة عن كل ملف في المشروع:
- عد دقيق لكل ملفات البايثون في كل المجلدات
- تحليل تفصيلي لكل ملف (الدوال، الكلاسات، الغرض)
- تكامل مع نظام MCP للمعرفة الخارقة
"""

import ast
import os
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

# المجلدات الرئيسية التي يجب تحليلها
TARGET_DIRECTORIES = ["app", "tests", "scripts", "microservices", "migrations"]


def _analyze_python_file(file_path: Path) -> dict[str, object]:
    """
    تحليل ملف بايثون واستخراج معلوماته التفصيلية.

    Args:
        file_path: مسار الملف

    Returns:
        dict: معلومات الملف (الدوال، الكلاسات، الـ imports، الغرض)
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)

        # استخراج المعلومات
        functions = []
        classes = []
        imports = []
        docstring = ast.get_docstring(tree) or ""

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_doc = ast.get_docstring(node) or ""
                functions.append(
                    {
                        "name": node.name,
                        "docstring": func_doc[:100] if func_doc else "",
                        "line": node.lineno,
                        "args_count": len(node.args.args),
                    }
                )
            elif isinstance(node, ast.ClassDef):
                class_doc = ast.get_docstring(node) or ""
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                classes.append(
                    {
                        "name": node.name,
                        "docstring": class_doc[:100] if class_doc else "",
                        "line": node.lineno,
                        "methods": methods[:10],  # أول 10 methods فقط
                    }
                )
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif node.module:
                    imports.append(node.module)

        return {
            "path": str(file_path),
            "name": file_path.name,
            "docstring": docstring[:200] if docstring else "",
            "functions_count": len(functions),
            "classes_count": len(classes),
            "functions": functions[:20],  # أول 20 دالة
            "classes": classes[:10],  # أول 10 كلاسات
            "imports_count": len(imports),
            "lines_count": len(content.splitlines()),
        }
    except Exception as e:
        logger.debug(f"تعذر تحليل الملف {file_path}: {e}")
        return {
            "path": str(file_path),
            "name": file_path.name,
            "error": str(e),
            "functions_count": 0,
            "classes_count": 0,
        }


def _analyze_directory(target_dir: Path, project_root: Path) -> dict[str, object]:
    """
    تحليل مجلد واستخراج إحصائيات الملفات.

    Args:
        target_dir: المجلد المستهدف
        project_root: جذر المشروع

    Returns:
        dict: إحصائيات المجلد
    """
    stats: dict[str, object] = {
        "python_files": 0,
        "directories": 0,
        "total_lines": 0,
        "total_functions": 0,
        "total_classes": 0,
        "files": [],
    }

    if not target_dir.exists():
        return stats

    for root, dirs, files in os.walk(target_dir):
        # تجاهل __pycache__ و .venv
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", ".git", "node_modules")]
        stats["directories"] += len(dirs)

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                stats["python_files"] += 1

                # تحليل الملف
                file_info = _analyze_python_file(file_path)
                relative_path = file_path.relative_to(project_root)
                file_info["relative_path"] = str(relative_path)

                stats["files"].append(file_info)
                stats["total_lines"] += file_info.get("lines_count", 0)
                stats["total_functions"] += file_info.get("functions_count", 0)
                stats["total_classes"] += file_info.get("classes_count", 0)

    return stats


def build_project_structure(project_root: Path) -> dict[str, object]:
    """
    يبني ملخصاً شاملاً ودقيقاً لبنية المشروع.

    يشمل التحليل:
    - جميع مجلدات المشروع (app, tests, scripts, microservices, migrations)
    - عد دقيق لكل ملفات البايثون
    - تحليل الدوال والكلاسات في كل ملف
    - إحصائيات شاملة

    Args:
        project_root: مسار جذر المشروع

    Returns:
        dict: معلومات شاملة عن بنية المشروع
    """
    structure: dict[str, object] = {
        "root": str(project_root),
        "python_files": 0,
        "directories": 0,
        "total_lines": 0,
        "total_functions": 0,
        "total_classes": 0,
        "by_directory": {},
        "main_modules": [],
    }

    # تحليل كل مجلد
    for dir_name in TARGET_DIRECTORIES:
        target_dir = project_root / dir_name
        if target_dir.exists():
            dir_stats = _analyze_directory(target_dir, project_root)
            structure["by_directory"][dir_name] = {
                "python_files": dir_stats["python_files"],
                "directories": dir_stats["directories"],
                "total_lines": dir_stats["total_lines"],
                "total_functions": dir_stats["total_functions"],
                "total_classes": dir_stats["total_classes"],
                # لا نضيف كل الملفات للحفاظ على الحجم
                "sample_files": [
                    {
                        "name": f["name"],
                        "relative_path": f["relative_path"],
                        "functions_count": f["functions_count"],
                        "classes_count": f["classes_count"],
                    }
                    for f in dir_stats["files"][:20]  # أول 20 ملف كعينة
                ],
            }

            # تجميع الإحصائيات الكلية
            structure["python_files"] = int(structure["python_files"]) + dir_stats["python_files"]
            structure["directories"] = int(structure["directories"]) + dir_stats["directories"]
            structure["total_lines"] = int(structure["total_lines"]) + dir_stats["total_lines"]
            structure["total_functions"] = (
                int(structure["total_functions"]) + dir_stats["total_functions"]
            )
            structure["total_classes"] = (
                int(structure["total_classes"]) + dir_stats["total_classes"]
            )

    # استخراج الوحدات الرئيسية من app
    app_dir = project_root / "app"
    if app_dir.exists():
        structure["main_modules"] = [
            d.name for d in app_dir.iterdir() if d.is_dir() and not d.name.startswith("__")
        ]

    logger.info(
        f"تم تحليل بنية المشروع: "
        f"{structure['python_files']} ملف بايثون، "
        f"{structure['total_functions']} دالة، "
        f"{structure['total_classes']} كلاس"
    )

    return structure


def build_microservices_summary(project_root: Path) -> dict[str, object]:
    """
    يبني ملخصاً شاملاً للخدمات المصغرة.

    Args:
        project_root: مسار جذر المشروع

    Returns:
        dict: معلومات عن الخدمات المصغرة
    """
    microservices_dir = project_root / "microservices"
    services: list[dict[str, object]] = []

    if microservices_dir.exists():
        for item in microservices_dir.iterdir():
            if item.is_dir() and not item.name.startswith((".", "__")):
                # تحليل كل خدمة
                service_info: dict[str, object] = {
                    "name": item.name,
                    "has_main": (item / "main.py").exists(),
                    "has_requirements": (item / "requirements.txt").exists(),
                    "python_files": 0,
                }

                # عد ملفات البايثون في الخدمة
                for _root, dirs, files in os.walk(item):
                    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv")]
                    service_info["python_files"] += sum(1 for f in files if f.endswith(".py"))

                services.append(service_info)

    services.sort(key=lambda x: x["name"])

    return {
        "root": str(microservices_dir),
        "total_services": len(services),
        "services": services,
        "services_names": [s["name"] for s in services],
    }


def get_file_details(project_root: Path, relative_path: str) -> dict[str, object]:
    """
    الحصول على تفاصيل ملف بايثون معين.

    Args:
        project_root: مسار جذر المشروع
        relative_path: المسار النسبي للملف

    Returns:
        dict: معلومات تفصيلية عن الملف
    """
    file_path = project_root / relative_path
    if not file_path.exists():
        return {"error": f"الملف غير موجود: {relative_path}"}

    return _analyze_python_file(file_path)


def search_files_by_name(project_root: Path, pattern: str) -> list[dict[str, str]]:
    """
    البحث عن ملفات بايثون بالاسم.

    Args:
        project_root: مسار جذر المشروع
        pattern: نمط البحث

    Returns:
        list: قائمة الملفات المطابقة
    """
    results = []
    pattern_lower = pattern.lower()

    for dir_name in TARGET_DIRECTORIES:
        target_dir = project_root / dir_name
        if target_dir.exists():
            for file_path in target_dir.rglob("*.py"):
                if pattern_lower in file_path.name.lower():
                    results.append(
                        {
                            "name": file_path.name,
                            "relative_path": str(file_path.relative_to(project_root)),
                            "directory": dir_name,
                        }
                    )

    return results[:50]  # أول 50 نتيجة فقط
