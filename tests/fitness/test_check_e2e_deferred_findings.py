"""اختبارات فارض التأجيل المُصرَّح — ISS-199.

تُثبت أنّ البوّابة **تحجب** لا أنّها تعمل فحسب (برهان D-270 L4 السلبي):

1. بلاغٌ مؤجَّلٌ **مُغلَق** (🟢) ⇒ خروجٌ غير صفري — التأجيل لا يُعمَّر بعد بلاغه (D-188).
2. بلاغٌ مؤجَّلٌ لا وجود له في `.memory/issues.md` ⇒ خروجٌ غير صفري — تأجيلُ عدم.
3. عنوانُ بلاغٍ بلا رمز حالة ⇒ خروجٌ غير صفري — الحالة تُصرَّح ولا تُستنتَج (D-206 L11).
4. سببُ تأجيلٍ أقصر من الحدّ ⇒ خروجٌ غير صفري — تصريحٌ لا يصرّح.
5. العدد المُجمَّد يخالف السجلّ **في الاتجاهين** ⇒ خروجٌ غير صفري (نمط D-189).
6. سكربتٌ يبني مخالفةً موسومةً ببلاغ ولا يستورد السجلّ ⇒ خروجٌ غير صفري (D-186).
7. سكربتٌ يتعذّر تحليله ⇒ خروجٌ غير صفري — البوّابة لا تشهد بما لم تقرأ (D-208 #6).
8. مستودعٌ سليم ⇒ خروجٌ صفري (لا إنذارٌ كاذب).

وتُثبت كذلك دلالة السجلّ نفسه: التغطية **كاملةٌ أو لا شيء** — مخالفةٌ تسمّي بلاغَين
وأحدهما غير مؤجَّل تبقى حاجبة، فلا يُعفي بلاغٌ مؤجَّلٌ رفيقَه بالمصادفة.

تُشغَّل على نُسَخٍ مؤقّتة داخل المستودع عبر إعادة توجيه مسارات الوحدة — لا تلمس ملفاً
حقيقياً.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_TMP = REPO_ROOT / ".tmp-deferred-gate-tests"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))
sys.path.insert(0, str(REPO_ROOT))

import check_e2e_deferred_findings as gate

from scripts.e2e.deferred_findings import (
    DEFERRED_FINDINGS,
    FROZEN_DEFERRED_COUNT,
    deferring_issues,
    split_problems,
)

_REASON = (
    "سببٌ منطوقٌ طويلٌ بما يكفي ليكون تصريحاً حقيقياً لا اعتذاراً: البلاغ مفتوحٌ "
    "بقرارٍ مكتوبٍ بتأجيل إصلاحه إلى جولته الخاصّة."
)

_OPEN_ISSUES = "## ISS-901 (2026-08-30) — عطبٌ مؤجَّلٌ عمداً — 🔴 مفتوح\n\nنصّ.\n"

#: سكربتٌ يبني نصّ مخالفةٍ موسوماً ببلاغ — الحرفية داخل شجرة البناء لا في تعليق.
_SCRIPT_TAGGED = 'def f():\n    return ["شظيّة (ISS-901)"]\n'
_SCRIPT_IMPORTING = (
    "from scripts.e2e.deferred_findings import split_problems\n\n"
    'def f():\n    return split_problems(["شظيّة (ISS-901)"])\n'
)
#: يذكر البلاغ في **تعليق** فقط — ليس إصداراً، فلا يُطالَب بالاستيراد.
_SCRIPT_COMMENT_ONLY = "# ملاحظة عن العطب (ISS-901)\ndef f():\n    return []\n"


@contextmanager
def _sandbox(
    tmp_path: Path,
    *,
    deferred: dict[str, str] | None = None,
    frozen: int | None = None,
    issues: str = _OPEN_ISSUES,
    scripts: dict[str, str] | None = None,
    issues_exists: bool = True,
) -> Iterator[None]:
    """مستودعٌ مصغّر داخل المستودع الحقيقي، ومسارات البوّابة مُعادٌ توجيهها إليه."""
    root = _TMP / tmp_path.name
    (root / ".memory").mkdir(parents=True, exist_ok=True)
    e2e = root / "scripts" / "e2e"
    e2e.mkdir(parents=True, exist_ok=True)

    registry = e2e / "deferred_findings.py"
    registry.write_text("# سجلٌّ صوريّ للاختبار\n", encoding="utf-8")
    for name, body in (scripts or {"probe.py": _SCRIPT_IMPORTING}).items():
        (e2e / name).write_text(body, encoding="utf-8")

    issues_path = root / ".memory" / "issues.md"
    if issues_exists:
        issues_path.write_text(issues, encoding="utf-8")

    payload = ({"ISS-901": _REASON} if deferred is None else deferred, frozen)

    def _fake_load() -> tuple[dict[str, str], int]:
        table, count = payload
        return dict(table), len(table) if count is None else count

    originals = (gate.MEMORY_ISSUES, gate.E2E_DIR, gate.REGISTRY, gate._load_registry)
    gate.MEMORY_ISSUES, gate.E2E_DIR, gate.REGISTRY = issues_path, e2e, registry
    gate._load_registry = _fake_load
    try:
        yield
    finally:
        (gate.MEMORY_ISSUES, gate.E2E_DIR, gate.REGISTRY, gate._load_registry) = originals
        shutil.rmtree(_TMP, ignore_errors=True)


def _run() -> tuple[int, list[str]]:
    """يُشغِّل البوّابة ويُعيد ``(رمز الخروج، نصوص الانتهاكات)``.

    ⛔ **الفشل وحده ليس برهاناً**: طفرتان على المصدر أثبتتا أنّ اختباراً يكتفي بـ
    ``!= 0`` يبقى أخضر بينما الفحص المقصود محذوف، لأن فحصاً آخر يلتقط الحالة لسببٍ
    مختلف. وهو صنف ISS-145 حرفيّاً — إغلاقٌ على معيارٍ خطأ. فكلّ برهانٍ سلبي هنا
    يؤكّد **نصّ** الانتهاك لا مجرّد وقوعه.
    """
    code = gate.main()
    return code, list(gate._FAILURES)


def test_healthy_registry_passes(tmp_path: Path) -> None:
    """سجلٌّ سليمٌ ببلاغٍ مفتوحٍ وسببٍ منطوق يمرّ — لا إنذارٌ كاذب."""
    with _sandbox(tmp_path):
        code, failures = _run()
        assert (code, failures) == (0, [])


def test_closed_issue_still_deferred_fails(tmp_path: Path) -> None:
    """بلاغٌ **مُغلَق** وما زال مؤجَّلاً ⇒ البوّابة تحجب — التأجيل لا يُعمَّر (D-188)."""
    closed = "## ISS-901 (2026-08-30) — عطبٌ عولج — 🟢 مُغلَق بـD-999\n"
    with _sandbox(tmp_path, issues=closed):
        code, failures = _run()
        assert code != 0
        assert any("مُغلَق" in f for f in failures), failures


def test_unknown_issue_fails(tmp_path: Path) -> None:
    """بلاغٌ مؤجَّلٌ لا عنوان له في `issues.md` ⇒ البوّابة تحجب — تأجيلُ عدم."""
    with _sandbox(tmp_path, issues="## ISS-902 (2026-08-30) — آخر — 🔴 مفتوح\n"):
        code, failures = _run()
        assert code != 0
        assert any("لا عنوان له" in f for f in failures), failures


def test_status_without_marker_fails(tmp_path: Path) -> None:
    """عنوانٌ بلا رمز حالة ⇒ البوّابة تحجب — الحالة تُصرَّح ولا تُستنتَج (D-206 L11)."""
    with _sandbox(tmp_path, issues="## ISS-901 (2026-08-30) — عطبٌ بلا حالةٍ مُعلَنة\n"):
        code, failures = _run()
        assert code != 0
        assert any("بلا رمز حالة" in f for f in failures), failures


def test_short_reason_fails(tmp_path: Path) -> None:
    """سببٌ أقصر من الحدّ ⇒ البوّابة تحجب — تصريحٌ لا يصرّح."""
    with _sandbox(tmp_path, deferred={"ISS-901": "لاحقاً"}):
        code, failures = _run()
        assert code != 0
        assert any("أقصر" in f for f in failures), failures


def test_frozen_count_too_high_fails(tmp_path: Path) -> None:
    """رقمٌ مُجمَّد أكبر من السجلّ ⇒ البوّابة تحجب — دَينٌ أُغلق بلا تحديث رقمه."""
    with _sandbox(tmp_path, frozen=2):
        code, failures = _run()
        assert code != 0
        assert any("FROZEN_DEFERRED_COUNT=2" in f for f in failures), failures


def test_frozen_count_too_low_fails(tmp_path: Path) -> None:
    """رقمٌ مُجمَّد أصغر من السجلّ ⇒ البوّابة تحجب — دَينٌ كبر بصمت (D-189)."""
    with _sandbox(tmp_path, deferred={"ISS-901": _REASON}, frozen=0):
        code, failures = _run()
        assert code != 0
        assert any("FROZEN_DEFERRED_COUNT=0" in f for f in failures), failures


def test_second_list_in_another_script_fails(tmp_path: Path) -> None:
    """سكربتٌ يبني مخالفةً موسومةً ولا يستورد السجلّ ⇒ البوّابة تحجب (D-186).

    ومعه سكربتٌ سليم: بدونه يحمرّ الفحص لسببٍ آخر («لا سكربت يقرأ السجلّ»).
    """
    scripts = {"rogue.py": _SCRIPT_TAGGED, "probe.py": _SCRIPT_IMPORTING}
    with _sandbox(tmp_path, scripts=scripts):
        code, failures = _run()
        assert code != 0
        assert any("rogue.py" in f and "قائمةٌ ثانية" in f for f in failures), failures


def test_unparsable_script_is_reported_not_swallowed(tmp_path: Path) -> None:
    """ملفٌّ يتعذّر تحليله ⇒ البوّابة تحجب **باسمه** — لا تشهد بما لم تقرأ (D-208 #6).

    ومعه سكربتٌ سليمٌ عمداً: بدونه يحمرّ الفحص لسببٍ آخر («لا سكربت يقرأ السجلّ»)
    فيمرّ البرهان زوراً وإن ابتُلع الاستثناء.
    """
    scripts = {"broken.py": "def f(:\n", "probe.py": _SCRIPT_IMPORTING}
    with _sandbox(tmp_path, scripts=scripts):
        code, failures = _run()
        assert code != 0
        assert any("broken.py" in f and "يتعذّر تحليله" in f for f in failures), failures


def test_comment_mention_is_not_an_emission(tmp_path: Path) -> None:
    """ذكرُ بلاغٍ في **تعليق** ليس إصداراً — لا يُطالَب باستيراد، ولا إنذارٌ كاذب.

    بوّابةٌ تصيح بلا ذئب تُدرَّب الناس على تجاهلها، وهو العطب الذي وُلدت هذه
    الدفعة لعلاجه — فدقّة الكشف جزءٌ من العقد لا تحسينٌ.
    """
    with _sandbox(
        tmp_path,
        scripts={"note.py": _SCRIPT_COMMENT_ONLY, "probe.py": _SCRIPT_IMPORTING},
    ):
        code, failures = _run()
        assert (code, failures) == (0, [])


def test_no_script_reads_the_registry_fails(tmp_path: Path) -> None:
    """لا سكربتَ واحداً يمرّ عبر السجلّ ⇒ البوّابة تحجب — فارضٌ بلا مرمى (ISS-148)."""
    with _sandbox(tmp_path, scripts={"note.py": _SCRIPT_COMMENT_ONLY}):
        code, failures = _run()
        assert code != 0
        assert any("بلا مرمى" in f for f in failures), failures


# ── دلالة السجلّ نفسه ────────────────────────────────────────────────────────


def test_mixed_issue_ids_stay_blocking() -> None:
    """مخالفةٌ تسمّي بلاغَين وأحدهما غير مؤجَّل تبقى حاجبة — لا إعفاءَ بالمصادفة."""
    problem = "دورٌ صامت: لا نصَّ ولا كائن (ISS-150 · ISS-154)"
    assert deferring_issues(problem) == frozenset()
    blocking, deferred = split_problems([problem])
    assert (len(blocking), len(deferred)) == (1, 0)


def test_untagged_contract_problem_is_blocking() -> None:
    """مخالفةُ العقد لا تسمّي بلاغاً — فهي حاجبةٌ دائماً."""
    blocking, deferred = split_problems(["إطاراتٌ نهائية = 0 والعقد يوجب **واحداً** (§6.5)"])
    assert (len(blocking), len(deferred)) == (1, 0)


def test_declared_finding_is_deferred() -> None:
    """المخالفة الموسومة ببلاغٍ مُصرَّحٍ تُبلَّغ ولا تحجب."""
    problem = "شظيّة لاتينية في ردٍّ عربي: 'or solution in' (ISS-150)"
    assert deferring_issues(problem) == frozenset({"ISS-150"})
    blocking, deferred = split_problems([problem])
    assert (len(blocking), len(deferred)) == (0, 1)


def test_frozen_count_matches_the_live_registry() -> None:
    """الرقم المُجمَّد في المستودع الحقيقي يطابق سجلَّه — يتقلّص فقط."""
    assert len(DEFERRED_FINDINGS) == FROZEN_DEFERRED_COUNT
