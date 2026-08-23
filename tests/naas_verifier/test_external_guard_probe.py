"""عقود مسبار الهدف الخارجي (D-285).

⛔ **لا تعتمد هذه الاختبارات على تثبيت الهدف الخارجي.** التبعية خارجيةٌ عمداً ولا
تدخل `requirements`، فاختبارٌ يشترطها يصير أحمرَ في CI لسببٍ لا علاقة له بالصحّة.
المُختبَر هنا **منطقُ الصدق**: القيود، وبناء المسار، ورفضُ الكتابة، وصفرُ خانةٍ فارغة.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    """يُحمِّل السكربت بمساره — فهو أداةُ بحثٍ لا حزمةً مستورَدة."""
    path = ROOT / "scripts/research/probe_external_guard.py"
    spec = importlib.util.spec_from_file_location("probe_external_guard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe_mod = _load_module()

from naas_verifier.core.constraint import Dimension, Outcome
from naas_verifier.core.verdict import verify

_VOIDED = {
    "term": "غبي",
    "rule_accepted_without_error": True,
    "term_present_in_wordset": True,
    "fires_on_bare_term": False,
    "censor_output": "غبي",
}
_ENFORCED = {**_VOIDED, "fires_on_bare_term": True, "censor_output": "****"}


def test_constraint_set_covers_all_five_dimensions() -> None:
    """⛔ مجموعةٌ تفحص المخرَج النهائي وحده مُصحِّحٌ لا مُتحقِّق (D-267 L3)."""
    assert probe_mod._constraint_set().covered == set(Dimension)


def test_accepted_but_unenforceable_rule_violates_the_intermediate_dimension() -> None:
    """القاعدة المقبولة غير القابلة للفرض **يجب** أن تكسر البُعد الوسطي."""
    verdict = verify(probe_mod._build_trajectory(_VOIDED), probe_mod._constraint_set())
    rows = {row.dimension: row.outcome for row in verdict.dimensions}
    assert rows[Dimension.INTERMEDIATE_CONSTRAINTS] is Outcome.VIOLATED
    assert verdict.outcome is Outcome.VIOLATED


def test_an_enforced_rule_does_not_violate_anything() -> None:
    """برهانٌ سلبي: لو فرض الحارسُ القاعدة، لَما بقي انتهاك.

    بدون هذا، «انتهاك» أعلاه قد يكون قيداً مكسوراً دائماً لا عطباً في الهدف.
    """
    verdict = verify(probe_mod._build_trajectory(_ENFORCED), probe_mod._constraint_set())
    assert verdict.outcome is Outcome.HOLDS


def test_no_dimension_is_silently_inconclusive() -> None:
    """بُعدٌ يقول «لا أعرف» على مسارٍ سليم عطبٌ في القيد لا في الهدف (D-215)."""
    verdict = verify(probe_mod._build_trajectory(_VOIDED), probe_mod._constraint_set())
    silent = [
        row.dimension.value for row in verdict.dimensions if row.outcome is Outcome.INCONCLUSIVE
    ]
    assert silent == [], f"dimensions reported INCONCLUSIVE on a valid trajectory: {silent}"


def test_every_unmeasured_class_declares_a_spoken_reason() -> None:
    """⛔ الخانة الفارغة تُقرأ نجاحاً (D-206 L11) — فكل غيابٍ يُصرَّح بسببه."""
    for row in probe_mod._class_rows(None):
        if row["status"] == "measured":
            continue
        if row["status"] == "target_unavailable":
            continue
        assert str(row.get("reason_ar", "")).strip(), f"{row['class_id']} has an empty reason"


def test_absent_target_is_reported_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    """هدفٌ غائب يُبلَّغ عنه ⇒ صفر أصنافٍ مقيسة، ⛔ ولا رقمٌ مُخترَع."""
    monkeypatch.setattr(probe_mod, "_load_target", lambda: None)
    report = probe_mod.probe()
    assert report["target_available"] is False
    assert report["classes_measured"] == 0
    assert report["classes_violated"] == 0
    assert report["mechanism"] is None


def test_json_run_refuses_to_clobber_a_real_measurement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """⛔ **برهانٌ سلبي: الرفض يحجب فعلاً، لا يكتفي بالطباعة.**

    أداةٌ تدهس دليلها الملتزَم حين تُشغَّل في المُفسِّر الخطأ أسوأ من أداةٍ لا تعمل،
    لأنّ الإتلاف صامت. هنا يُثبَت أنّها تُرجِع 1 و**لا يُنشَأ ملفّ**.
    """
    target = tmp_path / "EXTERNAL_GUARD_PROBE.json"
    monkeypatch.setattr(probe_mod, "_load_target", lambda: None)
    monkeypatch.setattr(probe_mod, "REPORT", target)

    assert probe_mod.main(["--json"]) == 1
    assert not target.exists(), "an unavailable target must not overwrite a real measurement"


def test_json_run_writes_when_the_target_is_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """الوجه الآخر للبرهان: لولا هذا لكان الرفضُ أعلاه «لا يكتب أبداً»."""
    target = tmp_path / "EXTERNAL_GUARD_PROBE.json"
    monkeypatch.setattr(probe_mod, "REPORT", target)
    monkeypatch.setattr(probe_mod, "probe", lambda: {"target_available": True, "ok": True})

    assert probe_mod.main(["--json"]) == 0
    assert target.exists()
