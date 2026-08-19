"""اختبارات بوّابة دستور الهوية المعرفية المحيطة — D-269 (ISS-192/193).

البند الأهمّ هنا **جدار الحجب**: المنصّة تخدم قاصرين، والقانون أن لا يعبر مسارَ
الطبقة الخامسة حرفٌ واحد من نصّ المحادثة. وقانونٌ كهذا يجب أن يُثبَت أنّه **يفشل**
عند خرقه — وإلّا فهو نيّةٌ مكتوبة لا حاجز.

⚠️ كلّ التجارب على نسخةٍ مؤقّتة من الشجرة.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_ambient_identity as gate

_TREES = ("shared", ".memory", "docs", "scripts", "tools", "config", "app")


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    for rel in _TREES:
        src = REPO_ROOT / rel
        if src.is_dir():
            shutil.copytree(
                src,
                tmp_path / rel,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".next", "node_modules"),
            )
    for req in REPO_ROOT.glob("requirements*.txt"):
        shutil.copy(req, tmp_path / req.name)
    return tmp_path


def _run(root: Path) -> tuple[int, str]:
    saved = (gate.REPO_ROOT, gate.LAYER_PACKAGE)
    gate.REPO_ROOT = root
    gate.LAYER_PACKAGE = root / "shared" / "ambient_memory"
    gate._FAILURES.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = gate.main()
    finally:
        gate.REPO_ROOT, gate.LAYER_PACKAGE = saved
        gate._FAILURES.clear()
    return code, buffer.getvalue()


def _truth(root: Path) -> Path:
    return root / ".memory" / "ambient_identity_truth.md"


def test_repository_is_green(sandbox: Path) -> None:
    code, out = _run(sandbox)
    assert code == 0, f"الأساس أحمر — كلّ ما بعده بلا معنى:\n{out}"


def test_content_wall_breach_is_red(sandbox: Path) -> None:
    """L2: ⛔ لا يعبر مسارَ الطبقة حرفٌ من نصّ المحادثة — والمنعُ بالنوع لا بالنيّة."""
    path = sandbox / "shared" / "ambient_memory" / "probe.py"
    path.write_text(
        path.read_text(encoding="utf-8") + "\ndef leak(content: str) -> str:\n    return content\n",
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "جدار الحجب مخروق" in out


def test_import_from_app_is_red(sandbox: Path) -> None:
    """D-189 البند 5: `shared/` لا يستورد `app` — الإعداد يُمرَّر وسيطاً."""
    path = sandbox / "shared" / "ambient_memory" / "probe.py"
    path.write_text(
        "from app.core.settings.base import get_settings\n" + path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "يستورد من `app`" in out


def test_seam_unit_with_code_is_red(sandbox: Path) -> None:
    """L7 (قاعدة D-210): وحدةٌ مُصنَّفة `SEAM` ولها كود ⇒ أحمر.

    الاتجاه الذي لا تغطّيه بوّابةٌ أخرى: كودٌ حيٌّ بلا حارسٍ ولا اختبار أسوأ من
    الغياب المُعلَن — وهو المسار الذي تسلّل منه الكتابة إلى طرفٍ ثالث لو تُرك.
    """
    (sandbox / "shared" / "ambient_memory" / "writer.py").write_text("X = 1\n", encoding="utf-8")
    code, out = _run(sandbox)
    assert code == 1
    assert "الغياب يُفحَص في الاتجاهين" in out


def test_new_sdk_dependency_is_red(sandbox: Path) -> None:
    """L8: ⛔ لا `honcho-ai` — SDK يبني عميلَه فيقطع سلسلة الأثر (D-189)."""
    path = sandbox / "requirements.txt"
    path.write_text(path.read_text(encoding="utf-8") + "\nhoncho-ai==1.0.0\n", encoding="utf-8")
    code, out = _run(sandbox)
    assert code == 1
    assert "ممنوعة (L8)" in out


def test_silent_row_deletion_is_red(sandbox: Path) -> None:
    """لا حذف صامت: حذفُ وحدةٍ يتطلّب تحديث العدّاد المُصرَّح."""
    path = _truth(sandbox)
    kept = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("| 7 |")
    ]
    path.write_text("\n".join(kept), encoding="utf-8")
    code, out = _run(sandbox)
    assert code == 1
    assert "عدد الصفوف" in out


def test_missing_evidence_path_is_red(sandbox: Path) -> None:
    """ISS-149: دليلٌ يجب أن يوجد — وإلّا شهد الجدولُ بما لم يره."""
    path = _truth(sandbox)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "`shared/ambient_memory/probe.py`", "`shared/ambient_memory/ghost.py`"
        ),
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "غير موجود على القرص" in out


def test_status_token_in_law_doc_is_red(sandbox: Path) -> None:
    """D-188/D-209: وثيقة القانون بلا حالة — خريطتان لنظامٍ واحد هي ISS-139."""
    path = sandbox / "docs" / "architecture" / "AMBIENT_COGNITIVE_IDENTITY.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n| وحدة | `ACTIVE` |\n", encoding="utf-8")
    code, out = _run(sandbox)
    assert code == 1
    assert "وثيقة قانونٍ تحمل عمود حالة" in out


def test_unfalsifiable_claim_is_red(sandbox: Path) -> None:
    """D-227: حدّ المصداقية على الوثائق المُعلَنة نفسها."""
    path = sandbox / "docs" / "adr" / "ADR-010-deepseek-harness-adoption.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nهذا النظام صفر أخطاء.\n", encoding="utf-8"
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "غير قابلة للتفنيد" in out


def test_ban_line_is_not_mistaken_for_a_claim(sandbox: Path) -> None:
    """عطبُ D-206 L8 حرفياً: أوّل نسخةٍ من هذا البند رفضت **نصّ القانون الذي يشرح المنع**.

    فسطرٌ يحمل ⛔ هو حظرُ العبارة لا ادّعاؤها — وبوّابةٌ تصرخ على القاعدة تُعطَّل بعد
    أسبوع، وبوّابةٌ مُعطَّلة أسوأ من غيابها.
    """
    path = sandbox / ".memory" / "ambient_identity_constitution.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n- ⛔ ممنوع القول إنّ النظام «صفر أخطاء».\n",
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 0, out


def test_seam_must_be_recorded(sandbox: Path) -> None:
    """ISS-193: تبنٍّ بلا مقعدٍ مُعلَن ولا ADR."""
    path = sandbox / "docs" / "architecture" / "EXTENSION_SEAMS.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("deepseek-harness", "something-else"),
        encoding="utf-8",
    )
    code, out = _run(sandbox)
    assert code == 1
    assert "غير مُسجَّل" in out
