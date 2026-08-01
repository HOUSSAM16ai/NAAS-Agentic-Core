"""اختبارات بوابة التحقق من انعدام حركة legacy لمدة 30 يومًا — مُصحَّحة في D-205.

الاختبار الأصلي كان سطراً واحداً: «تمرّ البوّابة». وقد مرّت — على ملفّ يقول عن نفسه
إنّه نائب، فطبعت «✅ مُتحقَّق». اختبارٌ يؤكّد النجاح لا يفحص شيئاً؛ ما يفحص هو أن
**يبقى النائب غيرَ مُعتَرَفٍ به قياساً**.
"""

from __future__ import annotations

import json

import scripts.fitness.check_legacy_traffic_zero_window as gate

MEASURED = {
    "status": "measured",
    "window_days": 30,
    "legacy_request_total_30d": 0,
    "legacy_ws_sessions_total_30d": 0,
    "legacy_traffic_ratio_30d": 0.0,
    "verified_by": "ops@example",
    "verified_at": "2026-08-01T00:00:00Z",
}


def _with_status(tmp_path, monkeypatch, payload: dict) -> None:
    path = tmp_path / "status.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(gate, "STATUS_FILE", path)


def test_the_committed_evidence_is_not_mistaken_for_a_measurement() -> None:
    """
    الملفّ المُلتزَم اليوم `status: not_measured`. لو عاد يوماً يُقرأ كقياسٍ صفري
    دون تتبّعٍ حقيقي، فهذا الاختبار هو ما يوقفه.
    """
    data = json.loads(gate.STATUS_FILE.read_text(encoding="utf-8"))
    assert gate.is_measured(data) is False


def test_an_unmeasured_file_does_not_block_ci_but_refuses_the_phase5_claim() -> None:
    assert gate.main() == 0
    assert gate.main(require_measured=True) == 1


def test_a_placeholder_verifier_is_not_a_verifier(tmp_path, monkeypatch) -> None:
    """العطب الأصلي حرفياً: `verified_by: ops-placeholder` وأصفارٌ تُقرأ كبرهان."""
    _with_status(tmp_path, monkeypatch, {**MEASURED, "verified_by": "ops-placeholder"})
    assert gate.main(require_measured=True) == 1


def test_a_missing_verified_at_is_not_a_verifier(tmp_path, monkeypatch) -> None:
    _with_status(tmp_path, monkeypatch, {**MEASURED, "verified_at": ""})
    assert gate.main(require_measured=True) == 1


def test_a_real_zero_measurement_passes(tmp_path, monkeypatch) -> None:
    _with_status(tmp_path, monkeypatch, MEASURED)
    assert gate.main(require_measured=True) == 0


def test_a_real_measurement_with_traffic_fails(tmp_path, monkeypatch) -> None:
    """الفحص الأصلي ما زال قائماً: قياسٌ حقيقي بحركةٍ غير صفرية يفشل."""
    _with_status(tmp_path, monkeypatch, {**MEASURED, "legacy_request_total_30d": 3})
    assert gate.main() == 1


def test_a_short_window_fails(tmp_path, monkeypatch) -> None:
    _with_status(tmp_path, monkeypatch, {**MEASURED, "window_days": 7})
    assert gate.main() == 1


def test_a_missing_file_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gate, "STATUS_FILE", tmp_path / "absent.json")
    assert gate.main() == 1
