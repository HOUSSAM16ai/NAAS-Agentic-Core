"""البوّابتان الجديدتان تفشلان فعلاً (D-228/D-229).

⛔ **بوّابةٌ خضراء دائماً ليست بوّابة.** كل بندٍ هنا يُثبَت بتجربةٍ سلبية: نُفسِد المُدخَل
عمداً ونتأكّد أن البوّابة تحمرّ. هذا شرطُ D-209 على كل فارضٍ جديد، ودرسُ ISS-148
(«فارضٌ بلا مرمى»): عقودٌ خضراء ومسارُ التسريب خارج مرماها.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTRINE_GATE = REPO_ROOT / "scripts/fitness/check_research_doctrines.py"
POISON_GATE = REPO_ROOT / "scripts/fitness/check_no_system_text_as_user.py"

LAW_DOC = REPO_ROOT / "docs/architecture/MEMORY_ARCHITECTURE_DOCTRINE.md"
STATE_DOC = REPO_ROOT / ".memory/memory_architecture_truth.md"
MARKERS_HOME = REPO_ROOT / "shared/memory/authorship.py"


def _run(gate: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(gate)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def restore():
    """يعيد أيّ ملفٍّ أُفسد عمداً — التجربة السلبية لا تترك أثراً."""
    saved: list[tuple[Path, str]] = []

    def _save(path: Path) -> None:
        saved.append((path, path.read_text(encoding="utf-8")))

    yield _save

    for path, original in reversed(saved):
        path.write_text(original, encoding="utf-8")


class TestGatesAreGreenOnTruth:
    def test_doctrine_gate_passes(self) -> None:
        result = _run(DOCTRINE_GATE)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_poison_gate_passes(self) -> None:
        result = _run(POISON_GATE)
        assert result.returncode == 0, result.stdout + result.stderr


class TestDoctrineGateFailsWhenItShould:
    def test_status_token_inside_law_doc_is_red(self, restore) -> None:
        """لا سُلَّم ثانٍ: الحالة لا تعيش في وثيقة القانون (D-188/D-209)."""
        restore(LAW_DOC)
        LAW_DOC.write_text(
            LAW_DOC.read_text(encoding="utf-8") + "\n| الطبقة | ACTIVE |\n",
            encoding="utf-8",
        )
        result = _run(DOCTRINE_GATE)
        assert result.returncode == 1
        assert "رمز حالة" in result.stdout

    def test_empty_gap_cell_is_red(self, restore) -> None:
        """الفراغ يُقرأ نجاحاً — فيُرفَض."""
        restore(STATE_DOC)
        text = STATE_DOC.read_text(encoding="utf-8")
        broken = text.replace(
            "| `ACTIVE` | مُلحَق-فقط ومُختبَر؛ ولا مراجعة دورية للتقادم داخل الصفوف نفسها |",
            "| `ACTIVE` |  |",
        )
        assert broken != text, "لم يُطابَق الصفّ المستهدف — حدِّث التجربة"
        STATE_DOC.write_text(broken, encoding="utf-8")
        result = _run(DOCTRINE_GATE)
        assert result.returncode == 1
        assert "الفجوة فارغة" in result.stdout

    def test_missing_evidence_file_is_red(self, restore) -> None:
        """حالةٌ أمام دليلٍ محذوف ادّعاءٌ لا حقيقة."""
        restore(STATE_DOC)
        text = STATE_DOC.read_text(encoding="utf-8")
        broken = text.replace(
            "`app/api/routers/customer_chat.py`", "`app/api/routers/deleted_file.py`"
        )
        assert broken != text
        STATE_DOC.write_text(broken, encoding="utf-8")
        result = _run(DOCTRINE_GATE)
        assert result.returncode == 1
        assert "لا واحد من الأدلّة المذكورة موجود" in result.stdout

    def test_silently_deleted_row_is_red(self, restore) -> None:
        """حذفُ صفٍّ بصمت قرارٌ يُخفى — يُرفَض حتى يُحدَّث العدّاد."""
        restore(STATE_DOC)
        lines = STATE_DOC.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [ln for ln in lines if not ln.strip().startswith("| 9 |")]
        assert len(kept) < len(lines)
        STATE_DOC.write_text("".join(kept), encoding="utf-8")
        result = _run(DOCTRINE_GATE)
        assert result.returncode == 1
        assert "لا حذف صامت" in result.stdout

    def test_cited_but_missing_gate_is_red(self, restore) -> None:
        """قانونٌ يُسمّي فارضاً غير موجود ليس مفروضاً (ISS-148)."""
        restore(LAW_DOC)
        LAW_DOC.write_text(
            LAW_DOC.read_text(encoding="utf-8")
            + "\n**الفارض:** `check_a_gate_that_does_not_exist`.\n",
            encoding="utf-8",
        )
        result = _run(DOCTRINE_GATE)
        assert result.returncode == 1
        assert "غير موجودة في scripts/fitness" in result.stdout


class TestPoisonGateFailsWhenItShould:
    def test_competing_marker_definition_is_red(self, restore) -> None:
        """مصدرٌ واحد للعلامات — نسختان تعنيان مساراً يمنع ومساراً يسمح."""
        rival = REPO_ROOT / "shared/memory/_rival_markers.py"
        rival.write_text('SYSTEM_AUTHORED_MARKERS = ("[توجيه تربوي]",)\n', encoding="utf-8")
        try:
            result = _run(POISON_GATE)
            assert result.returncode == 1
            assert "تعريفٌ مُنافس" in result.stdout
        finally:
            rival.unlink(missing_ok=True)

    def test_unguarded_save_message_is_red(self, restore) -> None:
        """كل كتابةِ رسالةٍ تمرّ بالحارس — وإلّا عاد ISS-146 صامتاً."""
        target = REPO_ROOT / "app/services/customer/chat_persistence.py"
        restore(target)
        text = target.read_text(encoding="utf-8")
        broken = text.replace(
            'assert_student_authored(content, where="customer.save_message")',
            "pass  # حارسٌ مُزال عمداً",
        )
        assert broken != text, "لم يُطابَق نداء الحارس — حدِّث التجربة"
        target.write_text(broken, encoding="utf-8")
        result = _run(POISON_GATE)
        assert result.returncode == 1
        assert "بلا نداء assert_student_authored" in result.stdout

    def test_unparseable_file_is_reported_not_swallowed(self, restore) -> None:
        """⛔ بوّابةٌ لا تقرأ ملفاً لا تشهد بنظافته (D-208 بند ٦)."""
        broken_file = REPO_ROOT / "shared/memory/_broken_syntax.py"
        broken_file.write_text("def (((\n", encoding="utf-8")
        try:
            result = _run(POISON_GATE)
            assert result.returncode == 1
            assert "تعذّر التحليل" in result.stdout
        finally:
            broken_file.unlink(missing_ok=True)


def test_no_stray_artifacts_left_behind() -> None:
    """التجارب السلبية لا تترك ملفّات — وإلّا سمّمت التشغيل التالي."""
    assert not (REPO_ROOT / "shared/memory/_rival_markers.py").exists()
    assert not (REPO_ROOT / "shared/memory/_broken_syntax.py").exists()
    assert shutil.which  # سكوتُ linter على الاستيراد المستعمل للتوثيق
