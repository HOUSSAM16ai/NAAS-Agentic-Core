"""D-210 — تجارب سلبية مُثبَتة لبوّابة عقيدة القيمة والإيراد.

**بوّابةٌ لم تُرَ حمراء ليست بوّابة.** كل حالةٍ هنا تكسر بنداً واحداً من عقد
`check_revenue_doctrine` على نسخةٍ من الشجرة، وتُثبت أن البوّابة تُفشِل CI — لأن الثمن
الثالث في عقيدة الهندسة هو **صمتٌ يُقرأ نجاحاً**، وهو يعيش داخل الفوارض نفسها (D-208).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts/fitness/check_revenue_doctrine.py"
STATE_DOC = Path(".memory/revenue_engine_truth.md")
VALUE_DOC = Path("docs/VALUE_DOCTRINE.md")
SPEC_DOC = Path("docs/REVENUE_ENGINE_SPEC.md")

#: ما تكسره الحالات فعلاً — يُنسَخ نسخاً حقيقياً. وما عداه رابطٌ رمزي إلى الشجرة
#: الحقيقية، فيبقى الاختبار سريعاً **ولا يفشل لسببٍ غير الذي يقيسه**: النسخة الجزئية
#: كانت تُبلِّغ «الدليل غير موجود» عن اثني عشر ملفاً لم يمسّها الاختبار.
_MATERIALISED: tuple[str, ...] = (
    "scripts/fitness",
    "shared/illusion",
    ".memory/revenue_engine_truth.md",
    "docs/VALUE_DOCTRINE.md",
    "docs/REVENUE_ENGINE_SPEC.md",
)


def _mirror(tmp_path: Path) -> Path:
    """يبني شجرةً قابلة للتعديل: نسخٌ حقيقي لما يُكسَر، وروابط رمزية لما عداه.

    ⚠️ `scripts/` يجب أن يكون مجلَّداً حقيقياً: البوّابة تشتقّ جذر المستودع من
    ``Path(__file__).resolve()``، و`resolve()` تتبع الروابط — فرابطٌ رمزي كان سيعيدها
    إلى المستودع الحقيقي وتُصبح كل الحالات بلا أثر.
    """
    root = tmp_path / "repo"
    root.mkdir()
    materialised = {Path(rel) for rel in _MATERIALISED}
    parents = {parent for rel in materialised for parent in rel.parents if parent != Path(".")}

    def build(rel: Path) -> None:
        source = REPO_ROOT / rel if rel != Path(".") else REPO_ROOT
        target = root / rel
        for child in source.iterdir():
            child_rel = rel / child.name if rel != Path(".") else Path(child.name)
            if child_rel in materialised:
                target.mkdir(parents=True, exist_ok=True)
                if child.is_dir():
                    shutil.copytree(child, root / child_rel)
                else:
                    shutil.copy2(child, root / child_rel)
            elif child_rel in parents:
                (root / child_rel).mkdir(parents=True, exist_ok=True)
                build(child_rel)
            else:
                target.mkdir(parents=True, exist_ok=True)
                (root / child_rel).symlink_to(child)

    build(Path("."))
    return root


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    """`sys.executable` لا `python` — قاعدة نظافة الاختبارات (D-105)."""
    return subprocess.run(
        [sys.executable, str(root / GATE.relative_to(REPO_ROOT))],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _mirror(tmp_path)


def test_pristine_mirror_is_green(repo: Path) -> None:
    """خطُّ الأساس: لولا هذا لكانت كل الحالات التالية «حمراء لسببٍ آخر»."""
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_evidence_file_is_red(repo: Path) -> None:
    """حالةٌ أمام ملفٍّ محذوف ادّعاءٌ لا برهان."""
    shutil.rmtree(repo / "shared/illusion")
    result = _run(repo)
    assert result.returncode == 1
    assert "غير موجود في المستودع" in result.stdout


def test_invented_status_is_red(repo: Path) -> None:
    """لا سُلَّم ثانٍ — «قيد العمل» ليست حالةً قانونية."""
    doc = repo / STATE_DOC
    doc.write_text(doc.read_text(encoding="utf-8").replace("| `SEAM` |", "| `قيد العمل` |", 1))
    result = _run(repo)
    assert result.returncode == 1
    assert "خارج السُّلَّم القانوني" in result.stdout


def test_empty_gap_cell_is_red(repo: Path) -> None:
    """الفراغ يُقرأ نجاحاً — وهو أخطر من `ABSENT` الصريحة."""
    doc = repo / STATE_DOC
    text = doc.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| 1 |"))
    doc.write_text(text.replace(line, line.rsplit("|", 2)[0] + "|  |"))
    result = _run(repo)
    assert result.returncode == 1
    assert "خانة الفجوة فارغة" in result.stdout


def test_silently_deleting_a_layer_is_red(repo: Path) -> None:
    """حذفُ صفٍّ مزعجٍ يُكشَف — العدد المُعلَن يُقارَن بالمقروء."""
    doc = repo / STATE_DOC
    text = doc.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| 6 |"))
    doc.write_text(text.replace(line + "\n", ""))
    result = _run(repo)
    assert result.returncode == 1
    assert "لا حذف صامت" in result.stdout


def test_status_column_inside_a_law_doc_is_red(repo: Path) -> None:
    """⛔ خريطتان لنظامٍ واحد = وكيلان يقرآن بناءَين مختلفين (ISS-139)."""
    doc = repo / VALUE_DOC
    doc.write_text(
        doc.read_text(encoding="utf-8")
        + "\n\n| الطبقة | الحالة |\n|---|---|\n| فجوة الوهم | `ACTIVE` |\n"
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "القانون لا يحمل حالات" in result.stdout


def test_citing_a_nonexistent_gate_is_red(repo: Path) -> None:
    """قانونٌ يستشهد بفارضٍ غير قائم أسوأ من قانونٍ بلا فارض."""
    doc = repo / SPEC_DOC
    doc.write_text(doc.read_text(encoding="utf-8") + "\n**الفارض:** `check_something_invented`.\n")
    result = _run(repo)
    assert result.returncode == 1
    assert "check_something_invented" in result.stdout


def test_a_unit_section_without_an_enforcer_line_is_red(repo: Path) -> None:
    """كل وحدةٍ تُسمّي فارضها أو تُعلن غيابه — الصمت يُقرأ انضباطاً وهو ليس كذلك (L11)."""
    doc = repo / SPEC_DOC
    text = doc.read_text(encoding="utf-8")
    start = text.index("## D-222)")
    end = text.index("## D-223)")
    section = text[start:end]
    stripped = section.replace("**الفارض:**", "الحارس:").replace("بلا فارضٍ آلي", "لاحقاً")
    doc.write_text(text[:start] + stripped + text[end:])
    result = _run(repo)
    assert result.returncode == 1
    assert "بلا سطر «**الفارض:**»" in result.stdout


def test_declared_absent_but_code_exists_is_red(repo: Path) -> None:
    """الاتجاه المعاكس: «مُصنَّفٌ غائباً وهو موجود» = كودٌ حيّ بلا حارسٍ ولا اختبار."""
    (repo / "shared/verify").mkdir(parents=True)
    (repo / "shared/verify/__init__.py").write_text("")
    result = _run(repo)
    assert result.returncode == 1
    assert "غيابٌ مُعلَن وهو موجود" in result.stdout


def test_a_planned_gate_that_now_exists_is_red(repo: Path) -> None:
    """القائمة تتقلّص فقط: بوّابةٌ أُنجزت ونُسي شطبها تُبقي الوثيقة تقلّل من حراستها."""
    (repo / "scripts/fitness/check_item_coverage.py").write_text("raise SystemExit(0)\n")
    result = _run(repo)
    assert result.returncode == 1
    assert "مُعلَنة «مُخطَّطة» وهي موجودة فعلاً" in result.stdout


def test_classifying_without_the_maturity_threshold_is_red(repo: Path) -> None:
    """تصنيفٌ بملاحظتين تقريرٌ كاذب — والقاعدة مفروضة على كل مسارٍ يبني تصنيفاً."""
    engine = repo / "shared/illusion/engine.py"
    text = engine.read_text(encoding="utf-8")
    engine.write_text(
        text + "\n\ndef sneaky(concept_id: str) -> ConceptIllusion:\n"
        "    return ConceptIllusion(concept_id, 1.0, 0.0, 1.0, Quadrant.DANGEROUS, 1)\n"
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "بلا فحص `MIN_OBS`" in result.stdout
