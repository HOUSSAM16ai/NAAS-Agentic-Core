"""اختبارات bootstrap المواضيع وبوّابة تكافؤها — D-204.

ملفّان تحت الاختبار لا يُشغَّلان في هذه البيئة (لا Docker daemon)، فالمُختبَر هنا هو ما
**يمكن** إثباته بلا وسيط: منطق سكربت الإنشاء (بـ`rpk` مزيّف)، وحساسية البوّابة للانحراف.

بوّابةٌ تمرّ دائماً لا تحرس شيئاً — لذلك كل فحصٍ هنا مقرونٌ بتجربة سلبية.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE = REPO_ROOT / "scripts/fitness/check_topic_contract_parity.py"
COMPOSE = REPO_ROOT / "docker-compose.yml"


def _load_gate():
    spec = importlib.util.spec_from_file_location("topic_parity_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ── سكربت إنشاء المواضيع ────────────────────────────────────────────────────────


def _bootstrap_script() -> str:
    """يستخرج سكربت الـbootstrap من compose ويفكّ هروب `$$` كما يفعل Docker."""
    text = COMPOSE.read_text(encoding="utf-8")
    start = text.index("        set -e\n        # `|| true` used to swallow")
    marker = "rpk topic list --brokers redpanda:9092"
    end = text.index(marker, start) + len(marker)
    body = text[start:end]
    body = "\n".join(
        line[8:] if line.startswith("        ") else line for line in body.splitlines()
    )
    return body.replace("$$", "$")


def _run_bootstrap(tmp_path: Path, rpk_behaviour: str) -> subprocess.CompletedProcess[str]:
    """يشغّل السكربت بـ`rpk` مزيّف يقرّر مصيره حسب اسم الموضوع."""
    stub = tmp_path / "rpk"
    stub.write_text(rpk_behaviour, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

    script = tmp_path / "bootstrap.sh"
    script.write_text(_bootstrap_script(), encoding="utf-8")

    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}")
    return subprocess.run(
        ["/bin/sh", str(script)], capture_output=True, text=True, env=env, check=False
    )


# المزيّفات تُميّز `topic create` عن `topic list`: الأخير ينجح دائماً في الواقع، وجعله
# يفشل يخلط عطب السكربت بعطب المزيّف (وقع ذلك فعلاً عند أوّل تشغيل).
_ALL_OK = """#!/bin/sh
echo ok
exit 0
"""
_ALL_EXIST = """#!/bin/sh
if [ "$2" = "create" ]; then
  echo "unable to create topic: TOPIC_ALREADY_EXISTS: Topic already exists."
  exit 1
fi
echo ok
exit 0
"""
_ONE_BROKEN = """#!/bin/sh
if [ "$2" = "create" ]; then
  case "$3" in
    *notifications*) echo "INVALID_PARTITIONS: bad"; exit 1 ;;
  esac
fi
echo ok
exit 0
"""


def test_a_clean_bootstrap_creates_every_topic(tmp_path) -> None:
    result = _run_bootstrap(tmp_path, _ALL_OK)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("created ") == 4


def test_re_running_the_bootstrap_is_idempotent(tmp_path) -> None:
    """إعادة التشغيل على مواضيع قائمة يجب أن تمرّ — وإلّا صار كل `up` ثانٍ فاشلاً."""
    result = _run_bootstrap(tmp_path, _ALL_EXIST)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("exists  ") == 4


def test_a_genuinely_failed_topic_stops_the_bootstrap(tmp_path) -> None:
    """
    هذا هو العطب الذي أُصلِح: `|| true` كانت تبتلع **كل** فشل، فيبدو المكدّس صحيحاً
    بينما موضوعٌ غير موجود يبتلع رسائله حتى ينتهي الاحتفاظ.
    """
    result = _run_bootstrap(tmp_path, _ONE_BROKEN)
    assert result.returncode == 1
    assert "FAILED to create cogniforge.notifications.requested.v1" in result.stderr


def test_the_bootstrap_no_longer_swallows_failures() -> None:
    """
    حارسٌ نصّي: عودة `|| true` تُعيد فئة العطب كاملةً.

    التعليقات مُستبعَدة — شرحُ العطب يذكره حرفياً، ومطابقةُ الشرح تجعل الحارس يفشل
    على نفسه (وقع ذلك عند أوّل تشغيل).
    """
    code = "\n".join(
        line for line in _bootstrap_script().splitlines() if not line.strip().startswith("#")
    )
    assert "|| true" not in code
    assert "exit 1" in code


# ── البوّابة ────────────────────────────────────────────────────────────────────


def test_the_gate_passes_on_the_current_tree() -> None:
    result = subprocess.run(
        [sys.executable, str(GATE)], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_gate_reads_all_four_topics_from_compose() -> None:
    """
    الحارس ضدّ عطبٍ وقع فعلاً: آخر سطرٍ في الحلقة ينتهي بـ`"; do` لا بعلامة اقتباس،
    فكانت القراءة الأولى تُسقِط `dead-letter` وتُبلِّغ عنه زوراً كغير مُنشأ.
    """
    assert len(_load_gate()._compose_specs()) == 4


def test_the_gate_compares_shape_not_only_names(monkeypatch) -> None:
    """اسمٌ مطابق بشكلٍ مختلف أسوأ من اسمٍ مفقود: الموضوع موجود والترتيب مكسور."""
    module = _load_gate()
    drifted = dict(module._compose_specs())
    topic = "cogniforge.product.events.v1"
    partitions, retention = drifted[topic]
    drifted[topic] = (partitions + 1, retention)
    monkeypatch.setattr(module, "_compose_specs", lambda: drifted)

    problems = module._shape_problems()
    assert any("الأقسام" in problem for problem in problems)


def test_a_retention_drift_is_caught(monkeypatch) -> None:
    module = _load_gate()
    drifted = dict(module._compose_specs())
    topic = "cogniforge.dead-letter.v1"
    partitions, retention = drifted[topic]
    drifted[topic] = (partitions, retention // 2)
    monkeypatch.setattr(module, "_compose_specs", lambda: drifted)

    assert any("يوماً" in problem for problem in module._shape_problems())


@pytest.mark.parametrize("missing", ["contract", "compose"])
def test_a_topic_missing_from_either_side_fails(monkeypatch, missing) -> None:
    module = _load_gate()
    if missing == "contract":
        monkeypatch.setattr(module, "_contract_channels", set)
    else:
        monkeypatch.setattr(module, "_compose_topics", set)
    assert module.main() == 1


def test_the_declared_specs_cover_every_topic() -> None:
    module = _load_gate()
    assert len(module._declared_specs()) == len(module._declared_topics())
