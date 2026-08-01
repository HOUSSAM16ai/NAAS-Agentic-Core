"""اختبارات قارئ مخرَجات أدوات البنية التحتية — D-204.

هذا الملفّ وُلِد من فشلٍ حيّ في CI. المحاولة الأولى قرأت صحّة Redpanda بشريحة ثابتة
(`out.split("Healthy:")[1][:20]`)، و`rpk` يُبطِّن عمود القيمة بأكثر من عشرين مسافة —
فكانت النافذة فراغاً، و«true» لا تظهر فيها أبداً. النتيجة: انتظارٌ حتى المهلة الكاملة
على عنقودٍ **صحيح تماماً**، ثمّ فشلٌ يبدو كأنّ الوسيط لم يُقلِع.

تنسيقُ أداةٍ خارجية لا يُفترَض — يُثبَّت في اختبار.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/verify_event_stack_docker.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_event_stack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


#: المخرَج الحقيقي لـ`rpk cluster health` — لاحظ عرض التبطين، فهو سبب العطب الأصلي.
RPK_HEALTHY = """CLUSTER HEALTH OVERVIEW
=======================
Healthy:                          true
Unhealthy reasons:                []
Controller ID:                    0
All nodes:                        [0]
All nodes down:                   []
Leaderless partitions:            []
Under-replicated partitions:      []
"""

RPK_UNHEALTHY = """CLUSTER HEALTH OVERVIEW
=======================
Healthy:                          false
Unhealthy reasons:                [leaderless_partitions]
Controller ID:                    -1
"""


def test_a_healthy_cluster_is_recognised_despite_wide_padding() -> None:
    """
    العطب الأصلي حرفياً: التبطين أعرض من ٢٠ محرفاً، فالشريحة الثابتة تفوّت `true`.
    """
    assert _load()._field_says(RPK_HEALTHY, "Healthy:", "true") is True


def test_an_unhealthy_cluster_is_not_mistaken_for_healthy() -> None:
    assert _load()._field_says(RPK_UNHEALTHY, "Healthy:", "true") is False


def test_the_unhealthy_reasons_line_does_not_satisfy_the_health_check() -> None:
    """
    «Unhealthy reasons:» يحتوي «healthy» — ومطابقةٌ غير سطريّة قد تلتقطه. السطر
    الصحيح وحده هو الذي يقرّر.
    """
    tricky = "Unhealthy reasons:   [true-ish nonsense]\nHealthy:   false\n"
    assert _load()._field_says(tricky, "Healthy:", "true") is False


def test_a_missing_field_is_not_healthy() -> None:
    """غياب الحقل ليس صحّة — الافتراض هو الفشل."""
    assert _load()._field_says("something else entirely", "Healthy:", "true") is False


def test_an_empty_output_is_not_healthy() -> None:
    assert _load()._field_says("", "Healthy:", "true") is False


def test_the_health_wait_is_shorter_than_the_overall_budget() -> None:
    """
    مهلة قراءةٍ طويلة تُخفي عطب تحليلٍ خلف انتظارٍ صامت. الفشل السريع يشخّص.
    """
    module = _load()
    assert module.HEALTH_TIMEOUT < module.TOTAL_TIMEOUT


def test_the_verifier_reports_raw_output_when_a_service_never_reports_healthy(
    monkeypatch,
) -> None:
    """
    رسالةٌ بلا دليل لا تُشخِّص. الفشل الأوّل في CI ضاع لأنّ المخرَج الخام لم يُطبَع —
    فصار السبب تخميناً.
    """
    module = _load()
    monkeypatch.setattr(module, "HEALTH_TIMEOUT", 0)
    monkeypatch.setattr(module, "docker_exec", lambda *_a, **_k: (1, "connection refused"))

    module._await_health("c", ("rpk",), lambda _out: False, "Probe")

    assert module._FAIL
    assert "connection refused" in module._FAIL[-1]


def test_a_service_that_becomes_healthy_is_reported_as_such(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "docker_exec", lambda *_a, **_k: (0, RPK_HEALTHY))

    module._await_health(
        "c", ("rpk",), lambda out: module._field_says(out, "Healthy:", "true"), "Probe"
    )

    assert module._PASS
    assert not module._FAIL


@pytest.mark.parametrize("command", ["docker_exec"])
def test_container_commands_are_argv_never_a_shell(command: str) -> None:
    """D-187: التنفيذ بـargv — الحقن غير مُمثَّل لا مُرشَّح."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert 'subprocess.run(\n            ["docker", "exec", container, *args]' in source
