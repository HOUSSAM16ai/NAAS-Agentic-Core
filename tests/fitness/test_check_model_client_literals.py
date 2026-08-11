"""اختبارات بوّابة حرفيات نموذج العميل — ISS-157.

حارسٌ لا يُثبَت أنه يصرخ ليس حارساً (D-207): الانتهاك الأصلي مزروعٌ هنا ويجب أن يُفشِلها.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_model_client_literals as gate
from _ast_util import UnparsableSourceError, parse_source

BANNED = "nvidia/nemotron-3-nano-30b-a3b:free"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (BANNED, True),
        ("openai/gpt-oss-20b:free", True),
        ("ORCHESTRATOR_LLM_MODEL", False),
        ("https://openrouter.ai/api/v1", False),
        ("a model with spaces:free", False),
    ],
)
def test_model_id_detection(value: str, expected: bool) -> None:
    """الكشف يُميّز مُعرَّف النموذج عن أيّ سلسلةٍ أخرى — لا إنذار كاذب."""
    assert gate._looks_like_model_id(value) is expected


def test_a_hardcoded_model_fails(monkeypatch, tmp_path, capsys) -> None:
    """الانتهاك الأصلي: الحرفية المحظورة تعود ⇒ أحمر."""
    client = tmp_path / "client.py"
    client.write_text(f'M = os.getenv("ORCHESTRATOR_LLM_MODEL", "{BANNED}")\n', encoding="utf-8")
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "MODEL_CLIENTS", ("client.py",))
    assert gate.main() == 1
    assert BANNED in capsys.readouterr().out


def test_reading_from_active_models_passes(monkeypatch, tmp_path) -> None:
    """الشكل الصحيح — وإلّا كانت بوّابةً تفشل دائماً فتُطفَأ."""
    client = tmp_path / "client.py"
    client.write_text(
        'M = os.getenv("ORCHESTRATOR_LLM_MODEL", ActiveModels.PRIMARY)\n', encoding="utf-8"
    )
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "MODEL_CLIENTS", ("client.py",))
    assert gate.main() == 0


def test_an_unparsable_file_raises_instead_of_reporting_clean(tmp_path: Path) -> None:
    """D-208 · البند ٦: بوّابةٌ لا تقرأ ملفاً لا تشهد بنظافته."""
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(UnparsableSourceError):
        parse_source(bad)


def test_the_real_client_carries_no_literal() -> None:
    """العقد الحيّ: العميل الحقيقي يقرأ من `ActiveModels`."""
    assert gate.main() == 0
