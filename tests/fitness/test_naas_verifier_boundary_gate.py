"""البرهان السلبي لبوّابة الحدّ المعماري — D-267 §3.1 · قفل D-187.

⛔ «اختبارٌ يستدعي البوّابة ويتوقّع نجاحها» يُثبِت أنّها **تعمل** لا أنّها **تحجب**.
كلّ فحصٍ هنا يبني شجرةً مؤقّتة تخرق بنداً واحداً ويؤكّد أنّ البوّابة تخرج بـ≠ 0.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_naas_verifier_boundary as boundary_gate

pytestmark = pytest.mark.skipif(
    sys.version_info < boundary_gate.MIN_PYTHON,
    reason="the gate refuses to certify below the project interpreter (PEP 695)",
)


def _run(tree: Path) -> tuple[int, str]:
    saved = (boundary_gate.REPO_ROOT, boundary_gate.PRODUCT_ROOT)
    boundary_gate.REPO_ROOT = tree
    boundary_gate.PRODUCT_ROOT = tree / "naas_verifier"
    boundary_gate._FAILURES.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = boundary_gate.main()
    finally:
        boundary_gate.REPO_ROOT, boundary_gate.PRODUCT_ROOT = saved
        boundary_gate._FAILURES.clear()
    return code, buffer.getvalue()


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """شجرةٌ صغيرة سليمة — ثمّ يخرقها كلّ فحصٍ ببندٍ واحد."""
    (tmp_path / "naas_verifier" / "core").mkdir(parents=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "microservices").mkdir()
    (tmp_path / "naas_verifier" / "core" / "verdict.py").write_text(
        "from dataclasses import dataclass\n", encoding="utf-8"
    )
    (tmp_path / "app" / "main.py").write_text("import json\n", encoding="utf-8")
    return tmp_path


def test_clean_tree_passes(tree: Path):
    code, output = _run(tree)
    assert code == 0, output


def test_product_importing_app_is_blocked(tree: Path):
    """L1/L2: مسار المنتج منفصلٌ بالتصميم."""
    (tree / "naas_verifier" / "leak.py").write_text(
        "from app.core import settings\n", encoding="utf-8"
    )
    code, output = _run(tree)
    assert code == 1
    assert "separate by design" in output


def test_core_importing_a_domain_module_is_blocked(tree: Path):
    """⛔ قلبٌ يعرف مجالاً بعينه ميزةٌ متنكّرة لا منتج."""
    (tree / "naas_verifier" / "core" / "leak.py").write_text(
        "from shared.curriculum import registry\n", encoding="utf-8"
    )
    code, output = _run(tree)
    assert code == 1
    assert "feature in disguise" in output


@pytest.mark.parametrize("module", ["subprocess", "httpx", "socket"])
def test_capability_import_is_blocked(tree: Path, module: str):
    """⛔ قفل D-187 مفروضٌ بنيوياً: لا مُنفِّذ ولا عميل شبكةٍ قبل M1→M4."""
    (tree / "naas_verifier" / "runner.py").write_text(f"import {module}\n", encoding="utf-8")
    code, output = _run(tree)
    assert code == 1
    assert "D-187 lock" in output


def test_reverse_import_from_student_path_is_blocked(tree: Path):
    """⛔ جدار الحجب (D-113 · D-196): الذخيرة لا تصل مسار الطالب أبداً."""
    (tree / "app" / "chat.py").write_text(
        "from naas_verifier.corpus import classes\n", encoding="utf-8"
    )
    code, output = _run(tree)
    assert code == 1
    assert "must never reach" in output


def test_unparseable_module_is_reported_not_swallowed(tree: Path):
    """⛔ بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف (D-208)."""
    (tree / "naas_verifier" / "broken.py").write_text("def (:\n", encoding="utf-8")
    code, output = _run(tree)
    assert code == 1
    assert "cannot certify" in output


def test_empty_product_tree_is_reported(tree: Path):
    """⛔ بوّابةٌ لا تقرأ شيئاً لا تشهد بنظافة شيء."""
    (tree / "naas_verifier" / "core" / "verdict.py").unlink()
    code, output = _run(tree)
    assert code == 1
    assert "no python modules" in output


def test_real_repository_tree_passes():
    code, output = _run(REPO_ROOT)
    assert code == 0, output
