"""اختبارات بوّابة تكافؤ الحجب — D-203.

بوّابةٌ تمرّ دائماً لا تحرس شيئاً. التجربة السلبية هنا إلزامية: تُحقَن انحرافة في نسخة
مؤقّتة ويُثبَت أنّ البوّابة تصير حمراء.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts/fitness/check_redaction_parity.py"


def _run_gate() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


def test_the_two_brains_currently_agree() -> None:
    """
    المونوليث والأوركستريتور يفرضان D-113 بنسختين. تطابق السياسة هو ما يمنع «مسارٌ
    يحجب ومسارٌ يسرّب» — والطالب لا يعرف أيّ عقلٍ أجابه.
    """
    result = _run_gate()
    assert result.returncode == 0, result.stdout + result.stderr


def test_injected_drift_turns_the_gate_red(tmp_path, monkeypatch) -> None:
    """التجربة السلبية: نمطٌ مُعدَّل في أحد العقلين ⇒ خروج 1 برسالة تسمّي الحرفية."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("redaction_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    drifted = tmp_path / "drifted_sanitizer.py"
    original = module.ORCHESTRATOR.read_text(encoding="utf-8")
    drifted.write_text(
        original.replace(
            '_NUM = r"[-+]?\\d[\\d.,]*\\s*(?:/\\s*\\d[\\d.,]*)?\\s*%?"',
            '_NUM = r"[-+]?\\d+"',
        ),
        encoding="utf-8",
    )
    assert drifted.read_text(encoding="utf-8") != original, "الحقن لم يغيّر شيئاً"

    monkeypatch.setattr(module, "ORCHESTRATOR", drifted)
    assert module.main() == 1


def test_a_missing_source_fails_rather_than_passing_vacuously(tmp_path, monkeypatch) -> None:
    """
    ملفٌّ مفقود يجب أن يُفشِل البوّابة. البوّابة التي تمرّ على مصدرٍ غائب أسوأ من غيابها:
    تُعطي طمأنينةً كاذبة (§0).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("redaction_gate_missing", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "MONOLITH", tmp_path / "nope.py")
    assert module.main() == 1
