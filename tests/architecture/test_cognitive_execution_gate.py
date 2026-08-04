"""D-224 — تجارب سلبية مُثبَتة لبوّابة محرّك التنفيذ المعرفي.

**بوّابةٌ لم تُرَ حمراء ليست بوّابة.** وأهمّ حالةٍ هنا هي الأخيرة: **قفل D-187**. الصندوق
التنفيذي مبنيٌّ ويشغّل `python`/`pip`/`git`/`npm`، والمسافة بين «قدرة» و«حادثة أمنية» هي
سطرُ استيرادٍ واحد. فالقفل يجب أن يُرى وهو يمنع، لا أن يُوصَف في وثيقة.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts/fitness/check_cognitive_execution.py"
STATE_DOC = Path(".memory/cognitive_execution_truth.md")
LAW_DOC = Path("docs/architecture/COGNITIVE_EXECUTION_ENGINE.md")

#: ما تكسره الحالات فعلاً يُنسَخ نسخاً حقيقياً؛ وما عداه رابطٌ رمزي.
#: ⚠️ `scripts/` يبقى نسخاً حقيقياً: البوّابة تشتقّ الجذر بـ`resolve()` التي تتبع
#: الروابط، فرابطٌ رمزي كان سيعيدها إلى المستودع الحقيقي وتُصبح كل الحالات بلا أثر.
_MATERIALISED: tuple[str, ...] = (
    "scripts/fitness",
    "app",
    ".memory/cognitive_execution_truth.md",
    "docs/architecture/COGNITIVE_EXECUTION_ENGINE.md",
)


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
    """خطُّ الأساس: لولاه لكانت كل الحالات «حمراء لسببٍ آخر»."""
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_evidence_file_is_red(repo: Path) -> None:
    """حالةٌ أمام ملفٍّ محذوف ادّعاءٌ لا برهان."""
    shutil.rmtree(repo / "app/services/agent_tools/sandbox")
    result = _run(repo)
    assert result.returncode == 1
    assert "غير موجود في المستودع" in result.stdout


def test_invented_status_is_red(repo: Path) -> None:
    """لا سُلَّم ثانٍ — «قيد العمل» ليست حالةً قانونية."""
    doc = repo / STATE_DOC
    doc.write_text(doc.read_text(encoding="utf-8").replace("| `PLANNED` |", "| `قيد العمل` |", 1))
    result = _run(repo)
    assert result.returncode == 1
    assert "خارج السُّلَّم القانوني" in result.stdout


def test_empty_gap_cell_is_red(repo: Path) -> None:
    doc = repo / STATE_DOC
    text = doc.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| 1 |"))
    doc.write_text(text.replace(line, line.rsplit("|", 2)[0] + "|  |"))
    result = _run(repo)
    assert result.returncode == 1
    assert "خانة الفجوة فارغة" in result.stdout


def test_silently_deleting_a_layer_is_red(repo: Path) -> None:
    doc = repo / STATE_DOC
    text = doc.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| 10 |"))
    doc.write_text(text.replace(line + "\n", ""))
    result = _run(repo)
    assert result.returncode == 1
    assert "لا حذف صامت" in result.stdout


def test_silently_deleting_a_market_horizon_is_red(repo: Path) -> None:
    """أفقُ سوقٍ يُحذَف بصمت = طموحٌ يُكتَم بدل أن يُصنَّف (D-209)."""
    doc = repo / STATE_DOC
    text = doc.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| 23 |"))
    doc.write_text(text.replace(line + "\n", ""))
    result = _run(repo)
    assert result.returncode == 1
    assert "الطموح لا يُحذف بصمت" in result.stdout


def test_status_column_inside_the_law_doc_is_red(repo: Path) -> None:
    """⛔ خريطتان لنظامٍ واحد = وكيلان يقرآن بناءَين مختلفين (ISS-139)."""
    doc = repo / LAW_DOC
    doc.write_text(
        doc.read_text(encoding="utf-8")
        + "\n\n| الطبقة | الحالة |\n|---|---|\n| الصندوق | `ACTIVE` |\n"
    )
    result = _run(repo)
    assert result.returncode == 1
    assert "القانون لا يحمل حالات" in result.stdout


def test_citing_a_nonexistent_gate_is_red(repo: Path) -> None:
    doc = repo / LAW_DOC
    doc.write_text(doc.read_text(encoding="utf-8") + "\n**الفارض:** `check_invented_thing`.\n")
    result = _run(repo)
    assert result.returncode == 1
    assert "check_invented_thing" in result.stdout


def test_a_layer_without_an_enforcer_line_is_red(repo: Path) -> None:
    """كل طبقةٍ تُسمّي فارضها أو تُعلن غيابه (D-206 · L11)."""
    doc = repo / LAW_DOC
    text = doc.read_text(encoding="utf-8")
    start = text.index("## 10) ")
    end = text.index("## 11) ")
    section = text[start:end].replace("**الفارض:**", "الحارس:").replace("بلا فارضٍ آلي", "لاحقاً")
    doc.write_text(text[:start] + section + text[end:])
    result = _run(repo)
    assert result.returncode == 1
    assert "بلا سطر «**الفارض:**»" in result.stdout


class TestD187Interlock:
    """⛔ القفل الأمني — أهمّ بندٍ في هذه البوّابة."""

    def test_wiring_an_llm_to_the_sandbox_is_red(self, repo: Path) -> None:
        """سطرُ استيرادٍ واحد هو المسافة بين قدرةٍ وحادثة — فيجب أن يُرى وهو يُمنَع."""
        offender = repo / "app/services/agent_tools/auto_solver.py"
        offender.write_text(
            "from app.services.agent_tools.sandbox import run_sandboxed\n"
            "from app.infrastructure.ai.simple_client import get_ai_client\n\n"
            "def solve(question: str) -> str:\n"
            "    code = get_ai_client().stream_chat(question)\n"
            "    return run_sandboxed(['python', '-c', code])\n",
            encoding="utf-8",
        )
        result = _run(repo)
        assert result.returncode == 1
        assert "قفل D-187 مخروق" in result.stdout
        assert "auto_solver.py" in result.stdout

    def test_sandbox_alone_is_fine(self, repo: Path) -> None:
        """القفل يمنع **الجمع** لا القدرة — وإلّا عطّل الصندوق المشروع."""
        (repo / "app/services/agent_tools/counter.py").write_text(
            "from app.services.agent_tools.sandbox import run_sandboxed\n\n"
            "def count() -> str:\n    return run_sandboxed(['ls'])\n",
            encoding="utf-8",
        )
        assert _run(repo).returncode == 0

    def test_llm_alone_is_fine(self, repo: Path) -> None:
        (repo / "app/services/agent_tools/narrator.py").write_text(
            "from app.infrastructure.ai.simple_client import get_ai_client\n\n"
            "def narrate(text: str) -> str:\n    return get_ai_client().stream_chat(text)\n",
            encoding="utf-8",
        )
        assert _run(repo).returncode == 0

    def test_an_exemption_without_a_reason_is_red(self, repo: Path) -> None:
        """⛔ إعفاءٌ بلا سببٍ منطوق = صمتٌ يُقرأ إذناً."""
        gate = repo / GATE.relative_to(REPO_ROOT)
        gate.write_text(
            gate.read_text(encoding="utf-8").replace(
                "_INTERLOCK_EXEMPTIONS: dict[str, str] = {}",
                '_INTERLOCK_EXEMPTIONS: dict[str, str] = {"app/kernel.py": ""}',
            )
        )
        result = _run(repo)
        assert result.returncode == 1
        assert "بلا سببٍ منطوق" in result.stdout

    def test_a_stale_exemption_is_red(self, repo: Path) -> None:
        """إعفاءٌ لم يعد لازماً يُحذَف — الأذونات لا تتراكم."""
        gate = repo / GATE.relative_to(REPO_ROOT)
        gate.write_text(
            gate.read_text(encoding="utf-8").replace(
                "_INTERLOCK_EXEMPTIONS: dict[str, str] = {}",
                '_INTERLOCK_EXEMPTIONS: dict[str, str] = {"app/kernel.py": "سببٌ قديم"}',
            )
        )
        result = _run(repo)
        assert result.returncode == 1
        assert "لم يعد لازماً" in result.stdout
