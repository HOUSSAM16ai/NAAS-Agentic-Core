"""ISS-140 ج (D-191) — الكمّامة يبرّرها المكوّن **المُسلَّم**، لا نيّة تسليمه.

## الكارثة الحيّة

طالب سأل «واش راك؟ عاونّي نفهم الاحتمالات» فتلقّى **45 حرفاً** فقط:
«إليك الشرح البصري المفصل للتمرين خطوة بخطوة 🪄». وفحص الإطار النهائي أظهر
``payload keys = ['content','conversation_id','request_id']`` — **لا `ui_component`
إطلاقاً**، و``content`` طوله **0**. أي أن الطالب قرأ وعداً بشرحٍ لا يصل.

## الجذر

``_stage_calculated_ui`` كان يبثّ المكوّن عبر ``_normalize_stream_event`` ثمّ **يرمي
حكمه**. والمُطبِّع يُسقط الحمولة إلى ``{"type": "noop"}`` في ثلاث حالات (حمولة ليست
dict · فشل تحقّق ``UIComponentPayload`` · ``props`` أكبر من 16KB)، والمستهلك في
``customer_chat.py`` يُسقط الـ``noop`` بصمت. وبعد سطور قليلة كان الوعد يُبَثّ **بلا
شرط**، ومعه إطار نهائي فارغ يُنهي الدور.

وعدٌ بلا حمولة أسوأ من خطأ صريح — وهو بالضبط ما يحرّمه §0: «لا فشل صامت».

## القاعدة الدائمة المحروسة هنا

> **لا يُبَثّ نصٌّ مرافق (companion_text) ولا تُغلَق الكمّامة إلا إذا غادر المكوّن
> العملية فعلاً.** سقوط الحمولة ⇒ لا وعد، ويبقى المسار حيّاً ليصل الطالبَ شرحٌ حقيقي.

الاختبار يعمل على **مرحلة الدور نفسها** التي يمرّ بها الطالب حيّاً (لا إعادة بناء
موازية للمنطق — درس D-186).
"""

from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.clients.orchestrator.turn_context import TurnContext

_URN = (
    "كيس يحتوي على 11 كرة: 4 حمراء و2 بيضاء و5 خضراء. "
    "نسحب 3 كرات في آن واحد. ما احتمال أن تكون من نفس اللون؟"
)


def _client():
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    return OrchestratorClient()


async def _run_stage(client, question: str) -> tuple[list[dict], TurnContext]:
    ctx = TurnContext(
        question=question,
        user_id=1,
        conversation_id=1,
        history_messages=[{"role": "user", "content": _URN}],
        context={},
    )
    events = [ev async for ev in client._stage_calculated_ui(ctx) if isinstance(ev, dict)]
    return events, ctx


def _deltas(events: list[dict]) -> str:
    return "".join(
        str((ev.get("payload") or {}).get("content", ""))
        for ev in events
        if ev.get("type") == "assistant_delta"
    )


class TestCompanionRequiresDeliveredPayload:
    def test_dropped_component_emits_no_promise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """المُطبِّع يُسقط الحمولة ⇒ صفر وعد، وصفر إطار نهائي، والمسار يبقى حيّاً."""
        client = _client()
        real_normalize = client._normalize_stream_event

        def _drop_ui(event):
            if isinstance(event, dict) and event.get("type") == "ui_component":
                return {"type": "noop", "payload": {}}
            return real_normalize(event)

        monkeypatch.setattr(client, "_normalize_stream_event", _drop_ui)

        events, ctx = asyncio.run(_run_stage(client, "لم أفهم شرح لي بصرياً"))

        assert not any(ev.get("type") == "ui_component" for ev in events), (
            "المكوّن أُسقِط — لا يجوز أن يظهر في الأحداث"
        )
        # القاعدة: لا وعدَ بشرحٍ بصري بلا حمولة.
        assert "🪄" not in _deltas(events), "وعدٌ بصري بُثَّ رغم سقوط الحمولة (ISS-140 ج)"
        assert not any(ev.get("type") == "assistant_final" for ev in events), (
            "إطار نهائي فارغ يُنهي الدور بعد سقوط الحمولة"
        )
        assert ctx.turn_complete is False, "الكمّامة أُغلقت بلا مكوّن مُسلَّم"

    def test_delivered_component_still_emits_promise(self) -> None:
        """المسار السليم لم يتغيّر: مكوّن مُسلَّم ⇒ الوعد + الإطار النهائي كما كانا."""
        client = _client()
        events, ctx = asyncio.run(_run_stage(client, "لم أفهم شرح لي بصرياً"))

        ui = [ev for ev in events if ev.get("type") == "ui_component"]
        if not ui:  # pragma: no cover — بيئة بلا محرّك رمزي صالح
            pytest.skip("لم يُبنَ مكوّن بصري في هذه البيئة")
        assert _deltas(events).strip(), "مكوّن مُسلَّم بلا نصّ مرافق"
        assert ctx.turn_complete is True
