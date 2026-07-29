"""اختبارات الغلاف المُصحَّح بالتتبّع وبوّابته — D-189 (دَين D4).

تُغطّي العقد الذي أُصلح: **مدّ** المُعرَّف الوارد لا توليد بديلٍ عنه (العطب الذي كان في
``notation_skill.resolve_via_service``)، ومهلة صريحة دائماً (لا انتظار مفتوح)، وratchet
ثنائي الاتجاه على الدَّين المُجمَّد.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_correlated_http as gate

from shared.http_client import (
    CORRELATION_HEADER,
    TRACEPARENT_HEADER,
    correlated_client,
    correlation_headers,
    current_correlation_id,
    set_correlation_provider,
)


@pytest.fixture(autouse=True)
def _isolate_provider():
    """يعزل المُزوِّد العالمي بين الاختبارات."""
    set_correlation_provider(None)
    yield
    set_correlation_provider(None)


# ── عقد المُعرَّف ─────────────────────────────────────────────────────────────────


def test_ambient_id_is_extended_not_replaced() -> None:
    """المُعرَّف المحيط يُمدّ — هذا جوهر الإصلاح (لا uuid جديد لكل نداء)."""
    set_correlation_provider(lambda: "turn-42")
    assert current_correlation_id() == "turn-42"
    assert correlation_headers()[CORRELATION_HEADER] == "turn-42"


def test_explicit_id_wins_over_ambient() -> None:
    """المستدعي أعرف بسياقه: الصريح يتقدّم على المحيط."""
    set_correlation_provider(lambda: "ambient")
    assert current_correlation_id("explicit") == "explicit"


def test_inbound_header_is_honoured_not_overwritten() -> None:
    """ترويسة واردة صريحة لا تُطمس بمُعرَّف مُولَّد."""
    set_correlation_provider(lambda: "ambient")
    headers = correlation_headers({CORRELATION_HEADER: "inbound-7"})
    assert headers[CORRELATION_HEADER] == "inbound-7"


def test_inbound_header_matched_case_insensitively() -> None:
    """HTTP غير حسّاس لحالة الأحرف — ولا يجوز أن ينتج مفتاحان للترويسة نفسها."""
    headers = correlation_headers({"x-correlation-id": "lower-1"})
    assert headers[CORRELATION_HEADER] == "lower-1"
    assert sum(1 for key in headers if key.lower() == CORRELATION_HEADER.lower()) == 1


def test_generation_is_last_resort_only() -> None:
    """بلا مُزوِّد وبلا وارد ⇒ يُولَّد مُعرَّف (تدهور رشيق، لا انفجار)."""
    generated = current_correlation_id()
    assert generated and generated != current_correlation_id()


def test_broken_provider_degrades_gracefully() -> None:
    """مُزوِّد يرفع استثناءً لا يُسقط النداء الصادر."""

    def exploding() -> str | None:
        raise RuntimeError("context unavailable")

    set_correlation_provider(exploding)
    assert current_correlation_id()


def test_traceparent_is_derived_from_the_same_id() -> None:
    """الأثر والسجلّ يُربطان بمُعرَّف واحد — لا هويّتان لنفس الدور."""
    headers = correlation_headers(correlation_id="abcdef0123456789")
    traceparent = headers[TRACEPARENT_HEADER]
    version, trace_id, span_id, flags = traceparent.split("-")
    assert version == "00"
    assert len(trace_id) == 32
    assert len(span_id) == 16
    assert flags == "01"
    assert trace_id.startswith("abcdef0123456789")


def test_traceparent_survives_non_hex_correlation_ids() -> None:
    """مُعرَّف غير سادس عشري (مثل uuid بشُرَط أو نصّ) لا يُنتج traceparent فاسداً."""
    version, trace_id, span_id, _ = correlation_headers(correlation_id="turn/42:خطأ")[
        TRACEPARENT_HEADER
    ].split("-")
    assert version == "00"
    assert len(trace_id) == 32
    assert len(span_id) == 16


def test_caller_headers_are_preserved() -> None:
    """ترويسات المستدعي الأخرى تبقى (مثل X-Service-Token)."""
    headers = correlation_headers({"X-Service-Token": "jwt-abc"})
    assert headers["X-Service-Token"] == "jwt-abc"


# ── عقد العميل ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_carries_the_headers_and_an_explicit_timeout() -> None:
    """العميل يخرج مُصحَّحاً بالتتبّع ومُقيَّداً بمهلة — لا انتظار مفتوح."""
    set_correlation_provider(lambda: "turn-99")
    async with correlated_client() as client:
        assert client.headers[CORRELATION_HEADER] == "turn-99"
        assert client.headers[TRACEPARENT_HEADER]
        assert client.timeout.read is not None


@pytest.mark.asyncio
async def test_timeout_none_means_explicit_default_not_unbounded() -> None:
    """``timeout=None`` تعني «الافتراضي الصريح»، لا انتظاراً مفتوحاً."""
    async with correlated_client(timeout=None) as client:
        assert client.timeout.read == pytest.approx(gate_default_timeout())


@pytest.mark.asyncio
async def test_header_actually_reaches_the_wire() -> None:
    """برهان طرف-إلى-طرف: الترويسة تصل فعلاً إلى الطلب المُرسَل."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    set_correlation_provider(lambda: "wire-7")
    async with correlated_client(transport=httpx.MockTransport(handler)) as client:
        response = await client.post("http://service.invalid/resolve", json={})

    assert response.status_code == 200
    assert seen[CORRELATION_HEADER.lower()] == "wire-7"
    assert seen[TRACEPARENT_HEADER]


def gate_default_timeout() -> float:
    """يقرأ المهلة الافتراضية من المصدر القانوني بدل تكرار الرقم."""
    from shared.http_client.correlated import DEFAULT_TIMEOUT_SECONDS

    return DEFAULT_TIMEOUT_SECONDS


# ── عقد البوّابة ──────────────────────────────────────────────────────────────────


def test_gate_passes_on_current_tree() -> None:
    """المستودع الحالي يمرّ — البوّابة لا تُنذر كذباً."""
    assert gate.main() == 0


def test_gate_counts_via_ast_not_grep(tmp_path: Path) -> None:
    """ذِكر ``httpx.AsyncClient(`` في تعليق أو نصّ لا يُحتسب انتهاكاً."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        '# httpx.AsyncClient( in a comment\nDOC = "httpx.AsyncClient("\n',
        encoding="utf-8",
    )
    assert gate._count_constructions(sample) == 0


def test_gate_detects_bare_imported_async_client(tmp_path: Path) -> None:
    """``from httpx import AsyncClient`` ثم ``AsyncClient(...)`` يُحتسب أيضاً."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        "from httpx import AsyncClient\n\n\nasync def go():\n    async with AsyncClient() as c:\n        return c\n",
        encoding="utf-8",
    )
    assert gate._count_constructions(sample) == 1


def test_allowed_factories_are_the_only_exemptions() -> None:
    """قائمة الاستثناءات صريحة ومحصورة — الغلاف ومصانع التجميع فقط."""
    assert "shared/http_client/correlated.py" in gate.ALLOWED_FACTORIES
    assert all(path.endswith(".py") for path in gate.ALLOWED_FACTORIES)
    assert not (set(gate.ALLOWED_FACTORIES) & set(gate.FROZEN_DEBT)), (
        "ملفّ لا يكون مصنعاً مصرَّحاً به ودَيناً مُجمَّداً في الوقت نفسه"
    )


def test_migrated_files_are_not_in_frozen_debt() -> None:
    """ما هُوجر في D-189 خرج من الدَّين — وإلا صار الرقم يسمح بردّة."""
    for migrated in (
        "app/infrastructure/clients/memory_client.py",
        "app/infrastructure/clients/auditor_client.py",
        "app/services/skills/notation_skill.py",
    ):
        assert migrated not in gate.FROZEN_DEBT
