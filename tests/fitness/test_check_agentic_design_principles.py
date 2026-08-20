"""اختبارات فارض دستور مبادئ تصميم الأنظمة الوكيلية — D-272.

تُثبت أن البوّابة **تحجب** لا أنها تعمل فحسب، وفق برهان D-270 L4 السلبي:
1. وثيقة القانون مفقودة ⇒ خروجٌ غير صفري (الدستور بلا فارضٍ ينحرف).
2. وثيقة الحالة مفقودة ⇒ خروجٌ غير صفري (الحقيقة بدون سجلٍّ كذبٌ).
3. قانونٌ بلا خطّ أساس الوكيل الواحد (D-272 L1/L2) ⇒ خروجٌ غير صفري.
4. قانونٌ بلا حصرٍ لبنية الوكيل الواحد على المهمة التسلسلية (D-272 L3/L4) ⇒
   خروجٌ غير صفري.
5. مستودعٌ سليم بمبدأه الكامل ⇒ خروجٌ صفري (لا إنذارٌ كاذب).

تُشغَّل على نُسَخٍ مؤقّتة عبر إعادة توجيه مسارات الوحدة — لا تلمس ملفات المستودع
الحقيقية.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_TMP = REPO_ROOT / ".tmp-gate-tests"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_agentic_design_principles as gate

_LAW_MIN = """---
law_id: D-272
status: enforced
severity: mandatory
measured_at: "2026-08-19"
model_version: "claude-3.5-sonnet"
last_recalibration: "2026-08-19"
decomposable: true
sequential: true
tool_count: 12
central_verifier: true
tokens_per_task_ratio: 1.0
max_agents: 3
domain_measured: true
permitted_architecture: single_agent
single_agent_baseline:
  description: خط أساس الوكيل الواحد على المعيار الحقيقي
  baseline_success_pct: 0.45
  justification_ar: فوق عتبة الـ45% يُبرَّر التعدد بحصيلة حقيقية
---
# دستور مبادئ تصميم الأنظمة الوكيلية (D-272)

المهمة التسلسلية محكومةٌ ببنية الوكيل الواحد صراحةً.
"""

_TRUTH_MIN = """# حالة دستور D-272
الحالة: مفعَّل.
"""


@contextmanager
def _sandbox(
    tmp_path: Path,
    *,
    law: str = _LAW_MIN,
    truth: str = _TRUTH_MIN,
    law_exists: bool = True,
    truth_exists: bool = True,
    sequential_guard: bool = True,
) -> Iterator[None]:
    """يُشيِّد مستودعًا مصغّرًا داخل المستودع الحقيقي (لكي تمرّ relative_to) ويُعيد توجيه مسارات البوّابة إليه."""
    tmp_path = _TMP / tmp_path.name
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "architecture").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".memory").mkdir(parents=True, exist_ok=True)
    law_path = tmp_path / "docs" / "architecture" / "AGENTIC_DESIGN_PRINCIPLES.md"
    truth_path = tmp_path / ".memory" / "agentic_design_principles_truth.md"
    if law_exists:
        body = (
            law
            if sequential_guard
            else law.replace(
                "المهمة التسلسلية محكومةٌ ببنية الوكيل الواحد صراحةً",
                "المهمة التسلسلية بلا حصرٍ صريحٍ لبنية الوكيل الواحد",
            )
        )
        law_path.write_text(body, encoding="utf-8")
    if truth_exists:
        truth_path.write_text(truth, encoding="utf-8")
    originals = (gate.LAW, gate.TRUTH)
    gate.LAW = law_path
    gate.TRUTH = truth_path
    try:
        yield
    finally:
        gate.LAW, gate.TRUTH = originals
        shutil.rmtree(_TMP, ignore_errors=True)


def test_complete_principles_pass(tmp_path: Path) -> None:
    """مستودعٌ يملك قانونًا وحالةً بمبادئ D-272 كاملةً يمرّ — لا إنذارٌ كاذب."""
    with _sandbox(tmp_path):
        assert gate.main() == 0


def test_missing_law_fails(tmp_path: Path) -> None:
    """وثيقة القانون غائبة ⇒ البوّابة تحجب (الخروج غير صفري)."""
    with _sandbox(tmp_path, law_exists=False):
        assert gate.main() != 0


def test_missing_truth_fails(tmp_path: Path) -> None:
    """وثيقة الحالة غائبة ⇒ البوّابة تحجب (الخروج غير صفري)."""
    with _sandbox(tmp_path, truth_exists=False):
        assert gate.main() != 0


def test_missing_single_agent_baseline_fails(tmp_path: Path) -> None:
    """قانونٌ بلا خطّ أساس الوكيل الواحد (D-272 L1/L2) ⇒ البوّابة تحجب."""
    broken = _LAW_MIN.replace("single_agent_baseline:", "baseline_removed:")
    with _sandbox(tmp_path, law=broken):
        assert gate.main() != 0


def test_sequential_guard_enforced(tmp_path: Path) -> None:
    """قانونٌ لا يحصر المهمة التسلسلية في بنية الوكيل الواحد (D-272 L3/L4)
    ⇒ البوّابة تحجب."""
    with _sandbox(tmp_path, sequential_guard=False):
        assert gate.main() != 0
