"""D-226 — تجارب سلبية: البوّابة ترى العودة إلى العمى.

العطب الأصلي لم يكن خطأً مرئياً بل **صمتاً**: `diagnose_root` يُرجِع `None` فيُقرأ
«لا جذر». فالبوّابة يجب أن تُثبَت وهي تمنع بالضبط الرجوع الذي أنتج ذلك الصمت.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts/fitness/check_prerequisite_single_graph.py"
SKILL = Path("app/services/skills/semantic_property_skill.py")

_MATERIALISED: tuple[str, ...] = ("scripts/fitness", "app", "shared")


def _mirror(tmp_path: Path) -> Path:
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
                    shutil.copytree(child, root / child_rel, symlinks=True)
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
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_reverting_the_traverser_to_one_graph_is_red(repo: Path) -> None:
    """التجربة المركزية: إعادةُ العمى الذي وُلد منه D-226 تُفشِل CI."""
    path = repo / SKILL
    text = path.read_text(encoding="utf-8")
    start = text.index("def _prerequisites_of(")
    end = text.index("def _concept_definition(")
    reverted = (
        "def _prerequisites_of(concept_id: str) -> tuple[str, ...]:\n"
        "    return tuple(\n"
        "        e.source\n"
        "        for e in MISCONCEPTION_EDGES\n"
        '        if e.relation == "prerequisite_of" and e.target == concept_id\n'
        "    )\n\n\n"
    )
    path.write_text(text[:start] + reverted + text[end:])
    result = _run(repo)
    assert result.returncode == 1
    assert "لا يقرأ الرسم القانوني" in result.stdout


def test_renaming_the_traverser_away_is_red(repo: Path) -> None:
    """مجتازٌ بلا حارسٍ يعود إلى العمى — فإعادة التسمية بصمت تُفشِل."""
    path = repo / SKILL
    path.write_text(
        path.read_text(encoding="utf-8").replace("def _prerequisites_of(", "def _prereqs_v2(")
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "غير موجودة" in result.stdout


def test_a_third_prerequisite_graph_is_red(repo: Path) -> None:
    """⛔ رسمٌ ثالث لعلاقةٍ واحدة يتفرّق حتماً (صنف D-193/D-186)."""
    (repo / "app/services/skills/another_graph.py").write_text(
        'EDGES = [{"relation": "prerequisite_of", "source": "a", "target": "b"}]\n',
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "رسمٌ ثالث" in result.stdout


def test_the_declared_homes_are_not_flagged(repo: Path) -> None:
    """البوّابة تمنع الثالث لا الاثنين المُصرَّحين — وإلّا رفضت الصواب."""
    result = _run(repo)
    assert result.returncode == 0
    assert "رسمٌ ثالث" not in result.stdout
