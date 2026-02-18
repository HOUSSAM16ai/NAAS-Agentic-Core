"""مساعدات توليد طابع زمني لمعرفة المشروع."""

from pathlib import Path


def build_project_timestamp(project_root: Path) -> str:
    """يبني طابعاً زمنياً لتحديث المشروع اعتماداً على مسار الجذر."""
    import os

    return str(os.path.getmtime(project_root))
