"""اختبارات بوّابة الترميز الواحد — لكلّ قانونٍ تجربةٌ سلبية مُثبَتة (ISS-156).

البوّابة وُلدت من عطبٍ حيّ لم تمسكه 1296 اختباراً أخضر: الوكيل كان يُسلسل الإطار،
وطبقة النقل تُسلسله ثانيةً، فرأى الطالب JSON خاماً و**خُزِّن المظروف في
`customer_messages`**. كشفه تشغيل المكدّس كاملاً بـPostgres حقيقي.

وحارسٌ لا يُثبَت أنه يصرخ ليس حارساً («الثمن الثالث» — D-207): فلكلّ قانونٍ هنا
انتهاكٌ مزروع يجب أن يُفشِل البوّابة.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_no_double_encoded_frames as gate
from _ast_util import UnparsableSourceError, parse_source

# ── القانون 1: المُنتِج لا يُسلسل ───────────────────────────────────────────────

SERIALIZED_FRAME = (
    "import json\n"
    "def _make_json_event(text):\n"
    '    return json.dumps({"type": "assistant_delta", "payload": {"content": text}}) + "\\n"\n'
)

FRAME_DICT = (
    "def _make_json_event(text):\n"
    '    return {"type": "assistant_delta", "payload": {"content": text}}\n'
)

PLAIN_DUMPS = "import json\ndef audit(payload):\n    return json.dumps({'id': 1, 'ok': True})\n"


def _service_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source: str) -> None:
    root = tmp_path / "src"
    (root / "api").mkdir(parents=True)
    (root / "producer.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(gate, "SERVICE_DIR", root)
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    boundary = root / "api" / "agent_chat_customer_stream.py"
    boundary.write_text(
        "def _already_a_frame(chunk):\n    return None\n"
        "def _classify_agent_chunk(chunk):\n"
        "    framed = _already_a_frame(chunk)\n"
        "    return None, chunk, False\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "BOUNDARY_FILE", boundary)


def test_a_producer_that_serializes_a_frame_fails(monkeypatch, tmp_path, capsys) -> None:
    """الانتهاك الأصلي حرفياً — `json.dumps({...type...}) + "\\n"`."""
    _service_dir(monkeypatch, tmp_path, SERIALIZED_FRAME)
    assert gate.main() == 1
    assert "مُسلسَلاً" in capsys.readouterr().out


def test_returning_the_frame_dict_passes(monkeypatch, tmp_path) -> None:
    """الشكل الصحيح — وإلّا كانت بوّابةً تفشل دائماً فتُطفَأ."""
    _service_dir(monkeypatch, tmp_path, FRAME_DICT)
    assert gate.main() == 0


def test_unrelated_json_dumps_is_not_flagged(monkeypatch, tmp_path) -> None:
    """`json.dumps` على قاموسٍ بلا مفتاح `type` ليس إطاراً — لا إنذار كاذب."""
    _service_dir(monkeypatch, tmp_path, PLAIN_DUMPS)
    assert gate.main() == 0


def test_the_transport_layer_is_allowed_to_serialize(monkeypatch, tmp_path) -> None:
    """`stream_serialization.py` هو الموضع الشرعي الوحيد للتسلسل."""
    root = tmp_path / "src"
    (root / "api").mkdir(parents=True)
    (root / "stream_serialization.py").write_text(SERIALIZED_FRAME, encoding="utf-8")
    monkeypatch.setattr(gate, "SERVICE_DIR", root)
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    boundary = root / "api" / "agent_chat_customer_stream.py"
    boundary.write_text(
        "def _already_a_frame(c):\n    return None\n"
        "def _classify_agent_chunk(c):\n    return _already_a_frame(c)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "BOUNDARY_FILE", boundary)
    assert gate.main() == 0


# ── القانون 2: حارس الحدود لا يُحذَف بصمت ───────────────────────────────────────


def test_deleting_the_boundary_guard_fails(monkeypatch, tmp_path, capsys) -> None:
    """الدفاع في العمق مفروضٌ بنيوياً — حذفه يُفشِل CI."""
    _service_dir(monkeypatch, tmp_path, FRAME_DICT)
    gate.BOUNDARY_FILE.write_text(
        "def _classify_agent_chunk(chunk):\n    return None, chunk, False\n", encoding="utf-8"
    )
    assert gate.main() == 1
    assert "_already_a_frame" in capsys.readouterr().out


def test_a_missing_classifier_fails(monkeypatch, tmp_path, capsys) -> None:
    """إعادة تسمية المُصنِّف بلا تحديث البوّابة تُقرأ صمتاً — فتُرفَض."""
    _service_dir(monkeypatch, tmp_path, FRAME_DICT)
    gate.BOUNDARY_FILE.write_text("def something_else(c):\n    return c\n", encoding="utf-8")
    assert gate.main() == 1
    assert "حارس الحدود مفقود" in capsys.readouterr().out


def test_an_unparsable_file_raises_instead_of_reporting_clean(tmp_path: Path) -> None:
    """D-208 · البند ٦: بوّابةٌ لا تقرأ ملفاً لا تشهد بنظافته."""
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(UnparsableSourceError):
        parse_source(bad)


# ── العقد الحيّ ─────────────────────────────────────────────────────────────────


def test_the_real_service_is_clean() -> None:
    """الشيفرة الحقيقية بعد الإصلاح — معيار القبول."""
    assert gate.main() == 0


def test_the_real_agent_returns_a_frame_not_a_string() -> None:
    """`_make_json_event` هي بؤرة ISS-156 — تُختبَر على الأصل لا على وصفٍ له."""
    from microservices.orchestrator_service.src.services.overmind.agents.orchestrator import (
        OrchestratorAgent,
    )

    event = OrchestratorAgent._make_json_event(None, "مرحبا")  # type: ignore[arg-type]
    assert isinstance(event, dict), "عاد التسلسل إلى المُنتِج — ISS-156"
    assert event == {"type": "assistant_delta", "payload": {"content": "مرحبا"}}
