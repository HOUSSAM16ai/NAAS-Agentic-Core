"""
اختبارات تكاملية: استدعاء تمرين BAC عبر WebSocket

يتحقق هذا الملف من أن الطالب يحصل على الإجابة الصحيحة
لكل سؤال من الأسئلة الأربعة المتعلقة بتمرين الدوال العددية 2016.

التشغيل:
    pytest tests/integration/test_bac_exercise_websocket.py -v

متطلبات:
    - الخادم يعمل على localhost:8000
    - مستخدم admin موجود (benmerahhoussam16@gmail.com / 1111)
    - OPENROUTER_API_KEY مضبوط في البيئة
"""

import asyncio
import json
import os

import httpx
import pytest

# تخطي الاختبارات إذا لم يكن الخادم يعمل
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_LIVE_TESTS") == "1",
    reason="SKIP_LIVE_TESTS=1",
)

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/admin/api/chat/ws"

# ─── helpers ──────────────────────────────────────────────────────────────────


def _get_fresh_token() -> str | None:
    """يجلب token جديد من الخادم. يُرجع None إذا كان الخادم لا يعمل."""
    try:
        resp = httpx.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "benmerahhoussam16@gmail.com", "password": "1111"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception:
        return None


async def _ws_send(
    token: str,
    question: str,
    conversation_id: int | None = None,
    timeout: float = 90.0,
) -> tuple[str, int | None]:
    """
    يرسل سؤالاً عبر WebSocket ويجمع الرد الكامل.

    يُرجع (response_text, conversation_id).
    """
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        pytest.skip("websockets غير مثبت")

    full: list[str] = []
    conv_id: int | None = conversation_id

    async with connect(
        WS_URL,
        subprotocols=["jwt", token],
        ping_interval=None,
        open_timeout=15,
    ) as ws:
        payload: dict[str, object] = {"question": question}
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id

        await ws.send(json.dumps(payload, ensure_ascii=False))

        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            ev = json.loads(raw)
            etype = ev.get("type", "")
            pdata = ev.get("payload") or ev

            if etype == "assistant_delta":
                full.append(pdata.get("content", ""))
            elif etype == "assistant_final":
                if pdata.get("content") and not full:
                    full.append(pdata["content"])
                conv_id = pdata.get("conversation_id") or conv_id
                break
            elif etype == "conversation_init":
                conv_id = pdata.get("conversation_id") or conv_id
            elif etype == "stream_end":
                conv_id = pdata.get("conversation_id") or conv_id
                break
            elif etype in ("error", "stream_error", "assistant_error"):
                pytest.fail(f"WebSocket error event: {json.dumps(pdata, ensure_ascii=False)[:300]}")

    return "".join(full), conv_id


# ─── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def token() -> str:
    """يجلب token مرة واحدة لكل الاختبارات في هذا الملف."""
    t = _get_fresh_token()
    if t is None:
        pytest.skip("الخادم لا يعمل على localhost:8000")
    return t


@pytest.fixture(scope="module")
def event_loop():
    """event loop مشترك لكل الاختبارات async في هذا الملف."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── اختبارات ─────────────────────────────────────────────────────────────────


class TestBACExercise2016WebSocket:
    """
    اختبارات تكاملية لتمرين الدوال العددية 2016 — الدورة الأولى — الموضوع الثاني — التمرين الرابع.

    كل اختبار يتحقق من سؤال واحد من الأسئلة الأربعة التي يطرحها الطالب.
    الاختبارات مرتبة ومتسلسلة — كل اختبار يستخدم conversation_id من السابق.
    """

    # conversation_id مشترك بين الاختبارات
    _conv_id: int | None = None

    @pytest.mark.asyncio
    async def test_t1_full_exercise_text(self, token: str) -> None:
        """
        T1: طلب نص التمرين الكامل.

        يجب أن يُرجع النظام نص الأجزاء I+II+III بدون YAML وبدون إجابة نموذجية.
        """
        resp, cid = await _ws_send(
            token=token,
            question="أعطني نص تمرين الدوال العددية لسنة 2016 الموضوع الثاني التمرين الرابع الدورة الأولى بالكامل",
        )
        TestBACExercise2016WebSocket._conv_id = cid

        # الرد غير فارغ
        assert len(resp) > 500, f"الرد قصير جداً: {len(resp)} حرف"

        # نص التمرين موجود
        assert "g(x)" in resp or "g\\\\(x\\\\)" in resp or "الدالة" in resp, \
            "نص التمرين لا يحتوي على الدالة g"
        assert "f(x)" in resp or "الدالة" in resp, "نص التمرين لا يحتوي على الدالة f"

        # لا YAML frontmatter
        assert "metadata:" not in resp, "YAML frontmatter يظهر للطالب"
        assert "render:" not in resp, "YAML render config يظهر للطالب"

        # لا إجابة نموذجية
        assert "عناصر الإجابة النموذجية" not in resp, \
            "الإجابة النموذجية تظهر مع نص التمرين"

        # لا تلوث من تمارين أخرى
        assert "bac2024" not in resp.lower(), "تمرين 2024 يظهر مع تمرين 2016"

        # لا LLM failure
        assert "System Alert" not in resp, "LLM provider فشل"
        assert "Unable to reach" not in resp, "LLM provider غير متاح"

    @pytest.mark.asyncio
    async def test_t2_question_only_no_solution(self, token: str) -> None:
        """
        T2: طلب السؤال الأول فقط بدون حل.

        يجب أن يُرجع نص السؤال I فقط — بدون أي حسابات أو نتائج.
        """
        if self._conv_id is None:
            pytest.skip("T1 لم ينجح — لا conversation_id")

        resp, cid = await _ws_send(
            token=token,
            question="أعطني السؤال الأول فقط بدون حل",
            conversation_id=self._conv_id,
        )
        TestBACExercise2016WebSocket._conv_id = cid

        assert len(resp) > 100, f"الرد فارغ أو قصير جداً: {len(resp)}"

        # يجب أن يحتوي على نص السؤال
        assert any(kw in resp for kw in ["g(x)", "الدالة", "احسب", "النهاية"]), \
            "الرد لا يحتوي على نص السؤال"

        # يجب ألا يحتوي على حسابات الحل
        solution_keywords = ["g(-1) =", "1 - e", "1-e", "≈ -1,718", "≈ -1.718",
                             "g(2) =", "5e^{-2}", "الإجابة النموذجية"]
        found = [kw for kw in solution_keywords if kw in resp]
        assert not found, f"الرد يحتوي على حل رغم الطلب بدون حل: {found}"

        # لا LLM failure
        assert "System Alert" not in resp

    @pytest.mark.asyncio
    async def test_t3_detailed_explanation(self, token: str) -> None:
        """
        T3: طلب شرح مفصل حسب المنهجية.

        يجب أن يشرح كل خطوة ويصل إلى نفس نتائج الإجابة النموذجية.
        """
        if self._conv_id is None:
            pytest.skip("T2 لم ينجح — لا conversation_id")

        resp, cid = await _ws_send(
            token=token,
            question="الآن اشرح لي السؤال الأول شرحاً مفصلاً حسب المنهجية خطوة بخطوة",
            conversation_id=self._conv_id,
        )
        TestBACExercise2016WebSocket._conv_id = cid

        # الشرح طويل كافٍ
        assert len(resp) >= 1500, f"الشرح قصير جداً: {len(resp)} حرف"

        # يصل إلى نتائج الإجابة النموذجية
        assert any(kw in resp for kw in ["1 - e", "1-e", "1+5e", "1 + 5e"]), \
            "الشرح لا يصل إلى g(-1)=1-e أو g(2)=1+5e^-2"
        assert any(kw in resp for kw in ["+\\infty", "+∞", "لانهاية", "+inf"]), \
            "الشرح لا يذكر lim(-inf)=+inf"
        assert "0" in resp, "الشرح لا يذكر g(0)=0"

        # لا YAML ولا LLM failure
        assert "metadata:" not in resp
        assert "System Alert" not in resp

    @pytest.mark.asyncio
    async def test_t4_deeper_explanation(self, token: str) -> None:
        """
        T4: طلب شرح شرح (تعمق أكثر).

        يجب أن يُقدّم المبررات الرياضية الكاملة.
        """
        if self._conv_id is None:
            pytest.skip("T3 لم ينجح — لا conversation_id")

        resp, cid = await _ws_send(
            token=token,
            question="شرح شرح — أريد تعمقاً أكثر في كل خطوة، لماذا نفعل هذا؟ ما المبرر الرياضي؟",
            conversation_id=self._conv_id,
        )

        # الشرح المعمق أطول
        assert len(resp) >= 2000, f"الشرح المعمق قصير جداً: {len(resp)} حرف"

        # يحتوي على مبررات رياضية
        assert any(kw in resp for kw in ["لوبيتال", "L'Hôpital", "مبرهنة", "نظرية", "مبرر"]), \
            "الشرح المعمق لا يحتوي على مبررات رياضية"

        # لا LLM failure
        assert "System Alert" not in resp
        assert "Unable to reach" not in resp


class TestWebSocketAuthProtocol:
    """
    يتحقق من بروتوكول المصادقة الصحيح للـ WebSocket.
    هذه الاختبارات تمنع تكرار أخطاء ISS-052.
    """

    @pytest.mark.asyncio
    async def test_subprotocol_auth_accepted(self, token: str) -> None:
        """
        يجب أن يقبل الخادم الاتصال عبر subprotocols=["jwt", token].
        هذا هو البروتوكول الوحيد الصحيح للعميل المباشر.
        """
        try:
            from websockets.asyncio.client import connect
        except ImportError:
            pytest.skip("websockets غير مثبت")

        connected = False
        async with connect(
            WS_URL,
            subprotocols=["jwt", token],
            ping_interval=None,
            open_timeout=10,
        ) as ws:
            connected = True
            # أرسل سؤالاً بسيطاً للتحقق
            await ws.send(json.dumps({"question": "مرحبا"}, ensure_ascii=False))
            # انتظر أول event
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            ev = json.loads(raw)
            assert ev.get("type") in (
                "conversation_init", "assistant_delta", "assistant_final"
            ), f"event غير متوقع: {ev.get('type')}"

        assert connected, "الاتصال لم يُقبل"

    @pytest.mark.asyncio
    async def test_event_payload_structure(self, token: str) -> None:
        """
        يجب أن تكون بنية الـ events: event["payload"]["content"]
        وليس event["content"] مباشرة.
        هذا يمنع تكرار ISS-052-D.
        """
        try:
            from websockets.asyncio.client import connect
        except ImportError:
            pytest.skip("websockets غير مثبت")

        delta_events: list[dict] = []

        async with connect(
            WS_URL,
            subprotocols=["jwt", token],
            ping_interval=None,
            open_timeout=10,
        ) as ws:
            await ws.send(json.dumps({"question": "قل مرحبا فقط"}, ensure_ascii=False))
            for _ in range(20):
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    ev = json.loads(raw)
                    if ev.get("type") == "assistant_delta":
                        delta_events.append(ev)
                    elif ev.get("type") in ("assistant_final", "stream_end"):
                        break
                except asyncio.TimeoutError:
                    break

        if delta_events:
            first = delta_events[0]
            # يجب أن يكون المحتوى تحت "payload"
            assert "payload" in first, \
                f"assistant_delta لا يحتوي على 'payload': {first}"
            assert "content" in first["payload"], \
                f"payload لا يحتوي على 'content': {first['payload']}"
            # يجب ألا يكون المحتوى في المستوى الأعلى مباشرة
            assert first.get("content") is None or first.get("content") == "", \
                "المحتوى في المستوى الأعلى — بنية غير متوقعة"
