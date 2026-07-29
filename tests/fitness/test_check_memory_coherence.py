"""اختبارات بوّابة تماسك الذاكرة — D-188.

تُثبت أن البوّابة **تلتقط** أصناف الانحراف الأربعة التي مرّت بصمت شهرين:

1. فهرس سيادي متقادم (``.memory/README.md`` يعلن قراراً أقدم من الواقع).
2. إدخال جديد مدسوس في وسط السجلّ (خرق «الأحدث أولاً»).
3. دستور يعود موسوعةً (تجاوز سقف الأسطر).
4. قفل جدول الحقيقة أقدم من آخر قرار.

وأنها **لا تُنذر كذباً** على مستودعٍ متماسك. البوّابة تُشغَّل على نُسخٍ مؤقّتة عبر إعادة
توجيه مسارات الوحدة — لا تلمس ملفّات المستودع الحقيقية.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_memory_coherence as gate

_INDEX_TEMPLATE = """# فهرس الذاكرة

| الملف | الدور | السلطة |
|-------|------|--------|
| `decisions.md` | سجلّ القرارات المعمارية D-001→**D-{decision:03d}** | سجلّ ملزِم |
| `issues.md` | سجلّ الكوارث ISS-001→**ISS-{issue:03d}** | سجلّ ملزِم |
"""

_DECISIONS_TEMPLATE = """# Architectural Decisions
## D-188 · قرار حديث (2026-07-29)

نص.

## D-187 · قرار أقدم (2026-07-28)

نص.
"""

_ISSUES_TEMPLATE = """# Issues
## ISS-139 (2026-07-29) — كارثة حديثة

نص.

## ISS-138 (2026-07-28) — كارثة أقدم

نص.
"""


@contextmanager
def _sandbox(
    tmp_path: Path,
    *,
    index_decision: int = 188,
    index_issue: int = 139,
    decisions: str = _DECISIONS_TEMPLATE,
    issues: str = _ISSUES_TEMPLATE,
    constitution_lines: int = 10,
    lock_date: str = "2026-07-29T10:00:00+00:00",
) -> Iterator[None]:
    """يبني مستودعاً مصغّراً ويُعيد توجيه مسارات البوّابة إليه."""
    (tmp_path / ".memory").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime").mkdir(parents=True, exist_ok=True)

    index = tmp_path / ".memory/README.md"
    index.write_text(
        _INDEX_TEMPLATE.format(decision=index_decision, issue=index_issue), encoding="utf-8"
    )
    decisions_path = tmp_path / ".memory/decisions.md"
    decisions_path.write_text(decisions, encoding="utf-8")
    issues_path = tmp_path / ".memory/issues.md"
    issues_path.write_text(issues, encoding="utf-8")

    constitution = tmp_path / "CLAUDE.md"
    constitution.write_text("قانون دائم\n" * constitution_lines, encoding="utf-8")

    lock = tmp_path / ".runtime/truth_table.lock.json"
    lock.write_text(json.dumps({"generated_at_utc": lock_date}), encoding="utf-8")

    originals = (
        gate.MEMORY_README,
        gate.DECISIONS,
        gate.ISSUES,
        gate.CLAUDE_MD,
        gate.TRUTH_LOCK,
    )
    gate.MEMORY_README = index
    gate.DECISIONS = decisions_path
    gate.ISSUES = issues_path
    gate.CLAUDE_MD = constitution
    gate.TRUTH_LOCK = lock
    try:
        yield
    finally:
        (
            gate.MEMORY_README,
            gate.DECISIONS,
            gate.ISSUES,
            gate.CLAUDE_MD,
            gate.TRUTH_LOCK,
        ) = originals


def test_coherent_memory_passes(tmp_path: Path) -> None:
    """مستودع متماسك يمرّ — البوّابة لا تُنذر كذباً."""
    with _sandbox(tmp_path):
        assert gate.main() == 0


def test_stale_sovereign_index_fails(tmp_path: Path) -> None:
    """الفهرس يعلن D-184 بينما السجلّ بلغ D-188 — عطب D-188 بعينه."""
    with _sandbox(tmp_path, index_decision=184):
        assert gate.main() == 1


def test_stale_issue_index_fails(tmp_path: Path) -> None:
    """الفهرس يعلن ISS-137 بينما السجلّ بلغ ISS-139."""
    with _sandbox(tmp_path, index_issue=137):
        assert gate.main() == 1


def test_id_mentioned_outside_index_row_does_not_rescue_a_stale_row(tmp_path: Path) -> None:
    """ذِكرُ المُعرَّف في فقرة أخرى لا يُثبت تحديث الفهرس (التجربة السلبية الأصلية)."""
    with _sandbox(tmp_path, index_decision=184):
        gate.MEMORY_README.write_text(
            gate.MEMORY_README.read_text(encoding="utf-8") + "\nملاحظة عابرة عن D-188.\n",
            encoding="utf-8",
        )
        assert gate.main() == 1


def test_decision_filed_out_of_order_fails(tmp_path: Path) -> None:
    """قرار أحدث مدسوس **تحت** قرار أقدم يخرق «الأحدث أولاً»."""
    out_of_order = """# Architectural Decisions
## D-187 · قرار أقدم (2026-07-28)

نص.

## D-188 · قرار حديث مدسوس في الأسفل (2026-07-29)

نص.
"""
    with _sandbox(tmp_path, decisions=out_of_order):
        assert gate.main() == 1


def test_constitution_bloat_fails(tmp_path: Path) -> None:
    """الدستور يتجاوز السقف ⇒ فشل (عقدٌ لا موسوعة)."""
    with _sandbox(tmp_path, constitution_lines=gate.CLAUDE_MD_MAX_LINES + 1):
        assert gate.main() == 1


def test_stale_truth_lock_fails(tmp_path: Path) -> None:
    """قفل جدول الحقيقة أقدم من آخر قرار ⇒ finding صريح."""
    with _sandbox(tmp_path, lock_date="2026-07-21T13:21:28+00:00"):
        assert gate.main() == 1


def test_missing_index_row_fails(tmp_path: Path) -> None:
    """حذف صفّ سجلّ ملزِم من الفهرس ⇒ فشل، لا تجاهل صامت."""
    with _sandbox(tmp_path):
        gate.MEMORY_README.write_text("# فهرس بلا جداول\n", encoding="utf-8")
        assert gate.main() == 1


@pytest.mark.parametrize("frozen_key", ["decisions.md", "issues.md"])
def test_frozen_order_debt_is_declared_for_both_logs(frozen_key: str) -> None:
    """الدَّين المُجمَّد مُعلَن صراحةً للسجلّين — قاعدة «يتقلّص فقط» تحتاج رقماً مرجعياً."""
    assert frozen_key in gate.FROZEN_ORDER_DEBT
    assert gate.FROZEN_ORDER_DEBT[frozen_key] >= 0
