"""اختبارات بوابة نظافة الاختبارات — D-105 (ISS-113).

تثبت أن البوابة تلتقط أنماط التسميم التي أسقطت CI (mock.Document في graph/search)
وتسمح بأنماط polyfill المشروعة (ModuleType مشروط بغياب التبعية).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

from check_test_hygiene import check_file


def _check(tmp_path: Path, source: str) -> list[str]:
    """يكتب مصدراً مؤقتاً تحت اسم مجموع ويُرجع انتهاكاته."""
    target = tmp_path / "tests" / "test_sample.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(source), encoding="utf-8")

    import check_test_hygiene as gate

    original_root = gate.REPO_ROOT
    gate.REPO_ROOT = tmp_path
    try:
        return check_file(target)
    finally:
        gate.REPO_ROOT = original_root


def test_unconditional_module_level_mock_write_is_violation(tmp_path: Path) -> None:
    """نمط scripts/test_search_pipeline.py الكارثي — تسميم غير مشروط بقيمة Mock."""
    violations = _check(
        tmp_path,
        """
        import sys
        from unittest.mock import MagicMock

        sys.modules["llama_index.core.schema"] = MagicMock()
        """,
    )
    assert len(violations) == 1
    assert "Mock" in violations[0]


def test_conditional_mock_write_is_still_violation(tmp_path: Path) -> None:
    """نمط scripts/test_super_reasoner.py — مشروط لكن بقيمة Mock تُظلِّل موديولاً حقيقياً."""
    violations = _check(
        tmp_path,
        """
        import sys
        from unittest.mock import MagicMock

        if "llama_index" not in sys.modules:
            sys.modules["llama_index"] = MagicMock()
        """,
    )
    assert len(violations) == 1


def test_conditional_moduletype_polyfill_is_allowed(tmp_path: Path) -> None:
    """polyfill مشروع: ModuleType مشروط بغياب التبعية — لا يُظلِّل شيئاً حقيقياً."""
    violations = _check(
        tmp_path,
        """
        import importlib.util
        import sys
        import types

        if importlib.util.find_spec("redis") is None:
            stub = types.ModuleType("redis")
            sys.modules["redis"] = stub
        """,
    )
    assert violations == []


def test_unconditional_moduletype_write_is_violation(tmp_path: Path) -> None:
    """حتى ModuleType غير المشروط على مستوى الوحدة تسميم وقت الجمع."""
    violations = _check(
        tmp_path,
        """
        import sys
        import types

        sys.modules["redis"] = types.ModuleType("redis")
        """,
    )
    assert len(violations) == 1
    assert "غير مشروط" in violations[0]


def test_in_function_mock_write_without_patch_dict_is_violation(tmp_path: Path) -> None:
    violations = _check(
        tmp_path,
        """
        import sys
        from unittest.mock import MagicMock

        def test_something():
            sys.modules["tavily"] = MagicMock()
        """,
    )
    assert len(violations) == 1
    assert "تسريب مضمون" in violations[0]


def test_in_function_mock_write_with_patch_dict_is_allowed(tmp_path: Path) -> None:
    """patch.dict في الملف = آلية استرجاع موجودة — مسموح."""
    violations = _check(
        tmp_path,
        """
        import sys
        from unittest.mock import MagicMock, patch

        def test_something():
            with patch.dict(sys.modules, {"tavily": MagicMock()}):
                pass
        """,
    )
    assert violations == []


def test_module_level_environ_write_outside_allowlist_is_violation(tmp_path: Path) -> None:
    violations = _check(
        tmp_path,
        """
        import os

        os.environ["SECRET_KEY"] = "rogue-value"
        """,
    )
    assert len(violations) == 1
    assert "allowlist" in violations[0]


def test_in_test_environ_write_is_not_module_level_violation(tmp_path: Path) -> None:
    """الكتابة داخل الاختبار يلتقطها fixture العزل في conftest — ليست انتهاك جمع."""
    violations = _check(
        tmp_path,
        """
        import os

        def test_something(monkeypatch):
            monkeypatch.setenv("SECRET_KEY", "scoped")
        """,
    )
    assert violations == []


def test_gate_passes_on_real_repository() -> None:
    """البوابة الحقيقية خضراء على المستودع الفعلي (لا انتهاكات قائمة)."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "fitness" / "check_test_hygiene.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"hygiene gate red:\n{result.stdout}\n{result.stderr}"
