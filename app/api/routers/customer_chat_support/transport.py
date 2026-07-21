"""WS transport primitives (locked send + keepalive + state) — sliced verbatim from customer_chat.py (D-173 Stage 2b).

قواعد D-168: هذه الوحدة لا تستورد `customer_chat` أبداً؛ الـ router يعيد
استيراد الرموز (re-export) فيبقى monkeypatch على `customer_chat.<name>`
فعّالاً لكل نداء يصدر من الـ handler (قانون late-binding).
"""

"""
واجهة برمجة تطبيقات محادثة العملاء القياسيين.

توفر نقاط النهاية الخاصة بالمستخدمين القياسيين للوصول إلى محادثة تعليمية
مع فرض سياسات الأمان والملكية.

## V46.0 — جدار الحماية المزدوج للقنوات

يُطبَّق OutputFirewall على complete_ai_response المُجمَّع قبل الحفظ في DB.
هذا يضمن أن أي HTML/JSX تسرَّب من LLM يُنظَّف قبل الوصول للطالب أو قاعدة البيانات.

D-086 (2026-05-23): تطبيق Protocol V46.0.
"""

import asyncio

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.di import get_logger

logger = get_logger(__name__)


TEXT_EVENT_TYPES = {"delta", "assistant_delta", "assistant_final"}


async def _locked_send_json(
    websocket: WebSocket,
    lock: asyncio.Lock,
    payload: dict[str, object],
) -> None:
    """
    إرسال JSON عبر WebSocket مع قفل تسلسلي لمنع تداخل البايتات.

    ─────────────────────────────────────────────────────────────────
    ISS-094 round 3 (D-096 — 2026-05-28): WS Send Concurrency Race
    ─────────────────────────────────────────────────────────────────

    Starlette's `WebSocket.send_json` لا يضمن thread/coroutine safety عند
    استدعاءات متزامنة على نفس الـ socket. السيناريو الكارثي:

      1. المستخدم يرسل سؤالاً
      2. `_evaluate_and_emit_bkt` يُطلَق كـ background task
         - يستدعي `await async_session_factory()` (DB query بطيء عبر Supabase)
         - ثم `await websocket.send_json({"type":"ui_component", ...})`
      3. بالتوازي، `stream_and_forward` يبدأ streaming deltas
         - يستدعي `await websocket.send_json({"type":"assistant_delta", ...})`
         - عشرات المرات
      4. **RACE**: BKT's send و stream's send يتزامنان على نفس asgi.send
      5. النتيجة الكارثية المحتملة:
         - WebSocket protocol corruption (interleaved frame bytes)
         - RuntimeError من asyncio (concurrent state machine updates)
         - silent close بـ code 1006/1011
      6. Frontend يرى WS close → reconnect → جديد قد يفشل لـ سبب آخر
      7. بعد 3 محاولات auth retries → auth_error → logout → kick to login

    لماذا SQLite لا يُظهر هذه الكارثة:
      - BKT يكتمل في <50ms (DB محلي)
      - stream يبدأ بعد BKT بكثير
      - لا تزامن فعلي → لا race

    لماذا Supabase يُسبب الكارثة:
      - BKT DB write يأخذ 300ms-2s عبر network
      - stream يبدأ فوراً ويستمر >5s
      - فرصة تزامن عالية على send_json

    D-118 (2026-06-17): بطاقات BKT/المسار لم تَعُد تُبثّ أثناء البثّ — تُقيَّم
    متزامنةً (`_evaluate_bkt_cards`، بلا send) وتُصدَر بعد الإطار النهائي للمحتوى.
    القفل يبقى ضرورياً للتزامن بين بثّ الـ deltas و keepalive (D-WS-FLAP-005)
    وإصدار البطاقات بعد النهاية — كل send يمرّ عبره (D-096).
    """
    async with lock:
        await websocket.send_json(payload)


def _is_text_event(event: dict[str, object]) -> bool:
    """يتحقق من أن الحدث نصي ومسموح بتجميعه داخل مخزن النص النهائي."""
    return str(event.get("type", "")) in TEXT_EVENT_TYPES


def _ws_is_connected(websocket: WebSocket) -> bool:
    """يتحقق من أن WebSocket لا يزال في حالة CONNECTED قبل أي send_json.

    D-WS-FLAP-001: يمنع RuntimeError عند محاولة الإرسال على socket مغلق،
    وهو السبب الجذري لنمط الـ flapping (يعمل → يتعطل → يعود).
    """
    return websocket.client_state == WebSocketState.CONNECTED


# ISS-098 (D-WS-FLAP-005 — 2026-05-29): فاصل الـ keepalive أثناء بثّ الدور.
_TURN_KEEPALIVE_INTERVAL_SECONDS = 20.0


async def _run_turn_keepalive(websocket: WebSocket, lock: asyncio.Lock) -> None:
    """يُرسل إطار pong خفيفاً كل ~20s أثناء بثّ دور المحادثة.

    الجذر (ISS-098): حلقة الاستقبال محجوبة طوال `await stream_task`، فلا
    يستطيع الخادم قراءة ping العميل والرد بـ pong. مع زمن Supabase + إجابة
    طويلة، يتجاوز الدور HEARTBEAT_TIMEOUT (90s) على العميل → close(1001)
    كاذب → reconnect → الإجابة الجارية تضيع.

    الحل: مهمة keepalive متزامنة تُرسل `pong` دورياً عبر نفس `send_lock`
    (فلا تتعارض مع إرسال الـ deltas — D-096). العميل يتعامل مع أي رسالة
    واردة كدليل حياة، وتحديداً `pong` يُلغي مؤقّت الـ heartbeat. تُلغى
    المهمة فور انتهاء البثّ. لا ترفع استثناءً للخارج أبداً.
    """
    try:
        while True:
            await asyncio.sleep(_TURN_KEEPALIVE_INTERVAL_SECONDS)
            if not _ws_is_connected(websocket):
                return
            try:
                await _locked_send_json(
                    websocket, lock, {"type": "pong", "payload": {"keepalive": True}}
                )
            except (WebSocketDisconnect, RuntimeError):
                return
            except Exception as exc:  # pragma: no cover - دفاعي
                logger.debug("customer_chat.keepalive_send_failed: %s", type(exc).__name__)
                return
    except asyncio.CancelledError:
        return
