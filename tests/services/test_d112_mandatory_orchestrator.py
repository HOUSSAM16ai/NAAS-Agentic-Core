"""D-112 — العمود الفقري الإلزامي (Microservices-Only · Hard-Fail).

عند تعذّر الـ orchestrator، النظام يُصدِر خطأً صريحاً (ORCHESTRATOR_REQUIRED) ولا
يسقط إلى local_graph (REQUIRE_ORCHESTRATOR=1 افتراضي). =0 يُعيد الـ fallback القديم.

التحقق الحي (2026-06-13): orchestrator UP → 44 deltas/إجابة؛ orchestrator DOWN →
error=ORCHESTRATOR_REQUIRED، صفر deltas، لا local. هذا الاختبار يحرس المنطق.
"""

from __future__ import annotations

import os

import pytest

from app.infrastructure.clients.orchestrator_client import OrchestratorClient


async def _collect(gen) -> list[dict]:
    events = []
    async for ev in gen:
        events.append(ev)
    return events


@pytest.mark.asyncio
async def test_hard_fail_when_orchestrator_unreachable(monkeypatch) -> None:
    """orchestrator غير متاح + REQUIRE_ORCHESTRATOR=1 ⇒ إطار error صريح، صفر local."""
    monkeypatch.setenv("REQUIRE_ORCHESTRATOR", "1")
    # عنوان مغلق حتماً → ConnectError سريع (لا شبكة).
    monkeypatch.setenv("ORCHESTRATOR_SERVICE_URL", "http://127.0.0.1:9")
    client = OrchestratorClient()
    # سؤال يتجاوز preempts (لا تحية/لا تمرين مُفهرَس/لا سياق احتمالات).
    events = await _collect(
        client.chat_with_agent(
            question="ما هو قانون نيوتن الثاني؟",
            user_id=1,
            conversation_id=1,
            history_messages=[],
        )
    )
    types = [e.get("type") for e in events if isinstance(e, dict)]
    # لا أي محتوى توليدي محلي.
    assert "assistant_delta" not in types, f"local fallback leaked: {types}"
    # إطار خطأ صريح بالرمز الإلزامي.
    errs = [e for e in events if isinstance(e, dict) and e.get("type") == "error"]
    assert errs, f"expected error frame, got {types}"
    code = (errs[-1].get("payload") or {}).get("code")
    assert code == "ORCHESTRATOR_REQUIRED", f"wrong code: {code}"


@pytest.mark.asyncio
async def test_rollback_flag_allows_fallback(monkeypatch) -> None:
    """REQUIRE_ORCHESTRATOR=0 ⇒ السلوك القديم (لا hard-fail) — rollback بلا deploy."""
    monkeypatch.setenv("REQUIRE_ORCHESTRATOR", "0")
    monkeypatch.setenv("ORCHESTRATOR_SERVICE_URL", "http://127.0.0.1:9")
    client = OrchestratorClient()
    events = await _collect(
        client.chat_with_agent(
            question="ما هو قانون نيوتن الثاني؟",
            user_id=1,
            conversation_id=1,
            history_messages=[],
        )
    )
    # في وضع rollback لا يُصدَر ORCHESTRATOR_REQUIRED (المسار القديم يعمل).
    codes = [
        (e.get("payload") or {}).get("code")
        for e in events
        if isinstance(e, dict) and e.get("type") == "error"
    ]
    assert "ORCHESTRATOR_REQUIRED" not in codes


def test_require_orchestrator_default_on() -> None:
    """الافتراضي مُفعَّل (1) ما لم يُضبط صراحةً."""
    val = os.environ.get("REQUIRE_ORCHESTRATOR", "1").strip().lower()
    assert val in ("0", "1", "true", "false", "yes", "no")
