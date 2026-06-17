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
import contextlib
import uuid
from datetime import UTC, datetime
from typing import NamedTuple

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.api.routers.ws_auth import WsActor, extract_websocket_auth
from app.api.schemas.customer_chat import (
    CustomerConversationDetails,
    CustomerConversationSummary,
)
from app.core.config import get_settings
from app.core.database import async_session_factory, get_db
from app.core.di import get_logger
from app.core.domain.chat import MessageRole
from app.core.domain.user import User
from app.deps.auth import CurrentUser, require_permissions
from app.infrastructure.clients.orchestrator_client import orchestrator_client
from app.services.analytics.bkt_persistence import BKTAnalyticsService
from app.services.auth.token_decoder import decode_token_payload
from app.services.boundaries.customer_chat_boundary_service import (
    CustomerChatBoundaryService,
)
from app.services.rbac import ADMIN_ROLE, QA_SUBMIT
from app.services.skills.ws_heartbeat_skill import handle_control_message
from app.telemetry.path_observer import close_ws_turn, open_ws_turn
from shared.chat_protocol.event_protocol import normalize_streaming_event

logger = get_logger(__name__)


def _apply_complete_response_firewall(text: str) -> str:
    """D-086 (V46.0): يُطبِّق OutputFirewall على الإجابة المكتملة قبل الحفظ.

    يُنظِّف HTML/JSX من complete_ai_response بعد اكتمال البث.
    Fail-open: أي فشل يُعيد النص الأصلي دون كسر المسار.
    """
    if not text or not text.strip():
        return text
    try:
        from app.services.skills.output_firewall import apply_channel_b_firewall

        cleaned, was_rejected = apply_channel_b_firewall(text, intent="educational")
        if was_rejected:
            logger.warning("customer_chat.complete_response_firewall_rejected chars=%d", len(text))
            return text  # fail-open
        return cleaned
    except Exception as exc:
        logger.debug("customer_chat.firewall_non_fatal: %s", exc)
        return text


def _strip_display_garbage(text: str) -> str:
    """D-115: مُطهّر العرض الحيّ المُصفّح — يحذف فواصل ⟦⟧ المشوّهة + تعليمات
    system prompt المُسرَّبة + أي رموز غريبة قبل عرضها للطالب. شبكة أمان فوق
    تنظيف الـ orchestrator. fail-open (لا يكسر البثّ).
    """
    if not text:
        return text
    try:
        from app.services.skills.content_integrity_skill import _strip_garbage_markers

        return _strip_garbage_markers(text)
    except Exception:
        return text


def _apply_final_answer_redaction(text: str, support_level: int | None) -> str:
    """D-114: حجب الإجابة النهائية الواعي بالفواصل على الإجابة المحفوظة.

    support_level==1 ⇒ يُعفي كتلة المثال المحلول (الملفوفة بالفواصل) ويحجب ما
    عداها؛ غير ذلك ⇒ حجب كامل (شبكة أمان D-113 + إزالة أي علامات شاردة). fail-open.
    """
    if not text or not text.strip():
        return text
    try:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        redacted, _ = redact_final_answers(text, support_level)
        return redacted
    except Exception as exc:
        logger.debug("customer_chat.final_redaction_non_fatal: %s", exc)
        return text


COMPATIBILITY_FACADE_MODE = True
# تنبيه معماري: هذا المسار واجهة توافقية فقط ويُمنع فيه أي تنفيذ محلي لمنطق الدردشة.
CANONICAL_EXECUTION_AUTHORITY = "orchestrator-service:/agent/chat"
LEGACY_LOCAL_EXECUTION_BLOCKED = True

router = APIRouter(
    prefix="/api/chat",
    tags=["Customer Chat"],
)

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


async def _persist_ui_component_cards(
    *,
    conversation_id: int,
    cards: list[dict[str, object]],
) -> None:
    """يحفظ بطاقات الـ Generative UI المستقلة كصفوف مساعد content="" (ISS-106).

    غير حرج: أي فشل يُسجَّل ولا يكسر الدور. كل بطاقة صف مستقل يحمل ui_component
    بالشكل السلكي ({component, props, fallback_text}) فتُصيَّر من التاريخ بعد إعادة الدخول.
    """
    valid = [
        c
        for c in cards
        if isinstance(c, dict) and isinstance(c.get("component"), str) and c["component"]
    ]
    if not valid:
        return
    try:
        async with async_session_factory() as db:
            persistence_service = CustomerChatBoundaryService(db)
            for card in valid:
                await persistence_service.save_message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content="",
                    ui_component=card,
                )
    except Exception as exc:
        logger.warning("ui_component_card_persist_failed: %s", exc, exc_info=True)


async def _evaluate_bkt_cards(
    *,
    user_id: int,
    conversation_id: int | None,
    question: str,
    history_messages: list[dict[str, str]],
) -> list[dict[str, object]]:
    """D-118: يقيّم تفاعل الطالب عبر BKTEngine ويبني حمولتَي بطاقتَي التتبّع.

    يُرجِع قائمة حمولات ``ui_component`` (bkt_hint_display + learning_path_card)
    **بلا بثّ ولا حفظ** — يقوم المنسّق بإصدارها وحفظها **بعد** الإطار النهائي
    للمحتوى (D-118) كي لا تُشظّي نص التمرين أثناء البثّ.

    الكتابة التحليلية (append-only — D-074) تحدث هنا (تُشغَّل متزامنة عبر
    ``create_task`` فلا تؤثّر TTFT). معزول كلياً: أي فشل (DB أو غيره) يُسجَّل
    ويُرجِع ما تجمّع — لا يكسر مسار المحادثة أبداً (D-074).
    """
    cards: list[dict[str, object]] = []
    try:
        async with async_session_factory() as bkt_db:
            evaluation = await BKTAnalyticsService(bkt_db).evaluate_and_record(
                user_id=user_id,
                session_id=conversation_id,
                question=question,
                history=history_messages,
            )
        cards.append(
            {
                "component": "bkt_hint_display",
                "props": {
                    "concept_id": evaluation.concept_id,
                    "cognitive_load_estimate": evaluation.cognitive_load_estimate,
                    "student_mastery_probability": (evaluation.student_mastery_probability),
                },
                "fallback_text": (
                    f"تتبّع المعرفة: {evaluation.concept_id} — "
                    f"إتقان {evaluation.student_mastery_probability:.0%}"
                ),
            }
        )
        # D-111: المسار التعلّمي التكيفي — يقترح الخطوة التالية فوق إتقان BKT.
        # معزول داخل suppress (لا يكسر بناء بطاقة BKT)؛ الـ Skill حتمي بلا I/O.
        with contextlib.suppress(Exception):
            from app.services.skills.learning_path_skill import (
                LearningPathInput,
                get_learning_path_skill,
            )

            path = get_learning_path_skill().derive(
                LearningPathInput(
                    concept_id=evaluation.concept_id,
                    mastery=evaluation.student_mastery_probability,
                )
            )
            cards.append(
                {
                    "component": "learning_path_card",
                    "props": {
                        "current_concept": path.current_concept,
                        "next_concept": path.next_concept,
                        "advanced": path.advanced,
                        "target_difficulty": path.target_difficulty,
                        "recommendation_text": path.recommendation_text,
                        "rationale": path.rationale,
                    },
                    "fallback_text": path.recommendation_text,
                }
            )
    except Exception as exc:
        # BKT must never break chat — log and return whatever accumulated.
        logger.warning("bkt_tracking_failed: %s", exc, exc_info=True)
    return cards


_PEDAGOGY_DIRECTIVE_TIMEOUT_S = 2.0

#: D-114: علامات الحيرة — تكرارها (2+) يفرض المثال المحلول (support_level=1).
_CONFUSION_MARKERS: tuple[str, ...] = (
    "لم أفهم",
    "لم افهم",
    "مفهمتش",
    "ما فهمت",
    "مافهمت",
    "ما افهم",
    "لا أفهم",
    "لا افهم",
    "صعب",
    "ماقدرت",
    "ما قدرت",
)


class _PedagogySnapshot(NamedTuple):
    """D-114: صورة المتعلم المُجمَّعة — تُمرَّر للسياق وتقود بوّابة المثال المحلول.

    ``support_level`` الافتراض الآمن = 5 (محجوب كلياً) عند أي تعذّر — لا 1 — كي
    لا يكشف فشلٌ واحد كل الإجابات (fail-closed).
    """

    directive_text: str
    support_level: int
    confusion_count: int
    concept_id: str
    mastery: float | None


def _count_confusion_signals(history_messages: list[dict[str, str]] | None, question: str) -> int:
    """يَعُدّ رسائل الطالب التي تُعبّر عن حيرة (السؤال الحالي + سجل المحادثة).

    حتمي، بلا I/O. تكرار الحيرة (≥2) ⇒ المبتدئ عالق ويحتاج مثالاً محلولاً.
    """
    texts: list[str] = [str(question or "")]
    for msg in history_messages or []:
        if isinstance(msg, dict) and msg.get("role") == "user":
            texts.append(str(msg.get("content") or ""))
    count = 0
    for text in texts:
        low = text.strip()
        if any(marker in low for marker in _CONFUSION_MARKERS):
            count += 1
    return count


async def _build_pedagogy_directive(
    *,
    user_id: int,
    question: str,
    history_messages: list[dict[str, str]],
) -> _PedagogySnapshot:
    """D-104/D-114: يقرأ صورة المتعلم من BKT ويشتق توجيهاً تربوياً + support_level.

    «المنسّق يملك صورة المتعلم» — قراءة الإتقان تقود سلوك المعلم: سقراطي للمتمكن،
    مثال محلول كامل للمبتدئ المطلق (D-114)، والتقاط المفاهيم الخاطئة قبل أن تتجذر.
    fail-open مطلق: أي تعذّر (DB/مهلة/تصنيف) ⇒ snapshot آمن (directive=""،
    support_level=5 محجوب كلياً) — التوجيه لا يكسر دور الطالب أبداً.
    """
    try:
        from app.services.skills.adaptive_pedagogy_skill import (
            PedagogyInput,
            get_adaptive_pedagogy_skill,
        )
        from app.services.skills.bkt_engine import (
            classify_concept_with_context,
            estimate_cognitive_load,
        )

        # ISS-112: تصنيف واعٍ بالسياق — «اشرح السؤال 2» يلتصق بمفهوم الحوار
        concept_id = classify_concept_with_context(question, history_messages)

        async def _read_snapshot() -> tuple[float | None, int]:
            async with async_session_factory() as ped_db:
                service = BKTAnalyticsService(ped_db)
                mastery = await service.latest_mastery(user_id, concept_id)
                count = await service.interaction_count(user_id, concept_id)
                return mastery, count

        mastery, interaction_count = await asyncio.wait_for(
            _read_snapshot(), timeout=_PEDAGOGY_DIRECTIVE_TIMEOUT_S
        )
        directive = get_adaptive_pedagogy_skill().derive(
            PedagogyInput(
                question=question,
                concept_id=concept_id,
                mastery=mastery,
                interaction_count=interaction_count,
                cognitive_load=estimate_cognitive_load(question),
            )
        )
        # D-114: الحيرة المتكرّرة تفرض المثال المحلول حتى لو الإتقان غير منخفض.
        confusion = _count_confusion_signals(history_messages, question)
        support_level = directive.support_level
        if confusion >= 2:
            support_level = 1
        logger.info(
            "pedagogy_directive level=%s support_level=%s concept=%s mastery=%s confusion=%s",
            directive.guidance_level,
            support_level,
            concept_id,
            f"{mastery:.2f}" if mastery is not None else "none",
            confusion,
        )
        return _PedagogySnapshot(
            directive_text=directive.directive_text,
            support_level=support_level,
            confusion_count=confusion,
            concept_id=concept_id,
            mastery=mastery,
        )
    except Exception as exc:
        logger.debug("pedagogy_directive_failed (fail-open): %s", exc)
        # fail-closed على support_level: 5 = محجوب كلياً (لا كشف عند الخطأ).
        return _PedagogySnapshot("", 5, 0, "general", None)


def get_chat_actor(
    current: CurrentUser = Depends(require_permissions(QA_SUBMIT)),
) -> CurrentUser:
    """تبعية تضمن امتلاك صلاحية الأسئلة التعليمية."""
    return current


def get_current_user_id(current: CurrentUser = Depends(get_chat_actor)) -> int:
    """إرجاع معرف المستخدم الحالي بعد تحقق الصلاحيات."""
    return current.user.id


async def get_actor_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    جلب كائن المستخدم الفعلي بعد التحقق من الحالة.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")
    await db.refresh(user)
    db.expunge(user)
    return user


def get_customer_service(
    db: AsyncSession = Depends(get_db),
) -> CustomerChatBoundaryService:
    """تبعية للحصول على خدمة حدود محادثة العملاء."""
    return CustomerChatBoundaryService(db)


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


def _bind_local_conversation_id(
    event: dict[str, object], conversation_id: int | None
) -> dict[str, object]:
    """يربط معرف المحادثة المحلي بجميع أحداث البث لمنع اختلاط السياق في الواجهة."""
    if conversation_id is None:
        return event
    payload = event.get("payload")
    if isinstance(payload, dict):
        payload["conversation_id"] = conversation_id
    else:
        event["payload"] = {"conversation_id": conversation_id}
    return event


def _bind_stream_metadata(
    event: dict[str, object],
    conversation_id: int | None,
    request_id: str | None,
) -> dict[str, object]:
    """يربط بيانات التتبع القياسية بكل حدث بث لعزل السياق بين الطلبات."""
    bound_event = _bind_local_conversation_id(event, conversation_id)
    if not request_id:
        return bound_event
    payload = bound_event.get("payload")
    if isinstance(payload, dict):
        payload["request_id"] = request_id
    else:
        bound_event["payload"] = {"request_id": request_id}
    return bound_event


def _extract_client_context_messages(payload: dict[str, object]) -> list[dict[str, str]]:
    """استخراج سياق المحادثة المرسل من الواجهة بشكل آمن ومحدود الحجم."""
    raw_context = payload.get("client_context_messages")
    if not isinstance(raw_context, list):
        return []

    sanitized: list[dict[str, str]] = []
    for item in raw_context:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        sanitized.append({"role": role, "content": text})
        if len(sanitized) >= 50:
            break
    return sanitized


def _merge_history_with_client_context(
    persisted_history: list[dict[str, str]],
    client_context: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    دمج تاريخ قاعدة البيانات مع سياق العميل مع منع تسريب رسائل محادثات أخرى.

    يعتمد على كشف التداخل بين ذيل persisted_history وبداية client_context
    لضمان أن الرسائل المضافة تنتمي فعلاً لنفس المحادثة.
    """
    if not client_context:
        return persisted_history
    if not persisted_history:
        return []

    persisted_tail = persisted_history[-3:] if len(persisted_history) >= 3 else persisted_history
    overlap_index: int | None = None
    max_start = len(client_context) - len(persisted_tail)
    for start in range(max_start, -1, -1):
        window = client_context[start : start + len(persisted_tail)]
        if window == persisted_tail:
            overlap_index = start + len(persisted_tail)
            break

    if overlap_index is None:
        return persisted_history

    safe_client_tail = client_context[overlap_index:][-12:]
    merged_history = list(persisted_history)
    for message in safe_client_tail:
        if message not in merged_history:
            merged_history.append(message)
    return merged_history[-80:]


def _try_build_math_ui_component(response_text: str) -> dict | None:
    """
    مُعطَّل عمداً (ISS-108 / D-097 — قرار المستخدم: «إيقاف التقطيع + بطاقات محقَّقة فقط»).

    كان يُمرِّر **نص الإجابة الحر** إلى ``math_pipeline._build_ui_component`` الذي
    يُقطّع النثر بـ regex فضفاضة فيُنتج «خطوات» عشوائية بلا معنى (مؤكَّد حياً على
    بيانات الإنتاج msg 3411: «بالعربي»، «أتمنى أن تكون الفكرة الآن واضحة») ويُصنّف
    شرح الاحتمالات كـ«معادلات». بطاقة ``math_explanation_card`` صالحة فقط لمخرَج
    محتوم منظَّم — لا لنثر LLM حر. البطاقات البصرية المحقَّقة (probability_tree /
    combinations_visualizer / full_exercise_story) تأتي من المسار المنفصل
    ``orchestrator_client._build_calculated_ui`` وتبقى عاملة.

    القاعدة الدائمة (D-097): ممنوع تقطيع نثر LLM حر إلى بطاقة خطوات. أي بطاقة
    Generative UI يجب أن تُبنى من بيانات محتومة مُتحقَّقة، لا من نص مُولَّد.
    """
    return None


async def _emit_terminal_frames(
    *,
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    pending_terminal_event: dict[str, object] | None,
    assistant_message_persisted: bool,
    complete_ai_response: str,
    stream_error: HTTPException | Exception | None,
    local_conversation_id: int | None,
    stream_request_id: str,
) -> None:
    """
    يضمن إرسال إطار نهائي واحد فقط لكل دور (assistant_final أو error)
    وإطار 'persisted' فقط بعد حفظ فعلي. لا يُسمح بالفشل الصامت
    الذي يبقي واجهة المستخدم في حالة تحميل أبدية (ISS-016/ISS-017).

    D-096: يستخدم send_lock لمنع التزامن مع BKT task و stream_and_forward.
    """
    if assistant_message_persisted:
        # بناء ui_component من النص المكتمل — لا يكسر المسار عند الفشل
        ui_component = _try_build_math_ui_component(complete_ai_response)

        if pending_terminal_event is not None:
            # حقن ui_component في الـ payload الموجود
            if ui_component and isinstance(pending_terminal_event.get("payload"), dict):
                pending_terminal_event["payload"]["ui_component"] = ui_component
            await _locked_send_json(websocket, send_lock, pending_terminal_event)
        else:
            payload: dict = {"content": ""}
            if ui_component:
                payload["ui_component"] = ui_component
            await _locked_send_json(
                websocket,
                send_lock,
                _bind_stream_metadata(
                    normalize_streaming_event({"type": "assistant_final", "payload": payload}),
                    local_conversation_id,
                    stream_request_id,
                ),
            )
        await _locked_send_json(
            websocket,
            send_lock,
            _bind_stream_metadata(
                normalize_streaming_event({"type": "persisted"}),
                local_conversation_id,
                stream_request_id,
            ),
        )
        return

    if isinstance(stream_error, HTTPException):
        details = str(stream_error.detail)
        status_code = stream_error.status_code
    elif complete_ai_response or pending_terminal_event is not None:
        details = "Failed to confirm assistant persistence before completion."
        status_code = 500
    elif stream_error is not None:
        details = "Stream interrupted before assistant response completed."
        status_code = 500
    else:
        details = "Assistant produced no response."
        status_code = 500

    await _locked_send_json(
        websocket,
        send_lock,
        _bind_stream_metadata(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {"details": details, "status_code": status_code},
                }
            ),
            local_conversation_id,
            stream_request_id,
        ),
    )


@router.websocket("/ws")
async def chat_stream_ws(
    websocket: WebSocket,
) -> None:
    """
    قناة WebSocket لبث محادثة تعليمية للمستخدم القياسي.

    D-WS-002: يجب استدعاء accept() قبل close() دائماً.
    استدعاء close() قبل accept() يُنتج HTTP 403 من uvicorn بدلاً من
    رسالة خطأ واضحة — هذا يُربك المتصفح ويُسبب reconnect loop.
    الحل: accept() أولاً ثم إرسال رسالة خطأ JSON ثم close().
    """
    token, selected_protocol = extract_websocket_auth(websocket)
    if not token:
        # D-WS-002: accept() أولاً لتجنب HTTP 403 من uvicorn
        await websocket.accept(subprotocol=selected_protocol)
        await websocket.send_json(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {
                        "details": "Authentication required. Please log in.",
                        "code": "WS_AUTH_MISSING",
                        "status_code": 4401,
                    },
                }
            )
        )
        await websocket.close(code=4401)
        return

    # ISS-100 (D-WS-CONN-001 — 2026-05-29): الهوية من الـ JWT فقط — بلا أي
    # استعلام لقاعدة البيانات عند الاتصال.
    #
    # الكارثة المُصلَحة (تأرجح متصل/غير متصل + لا إجابة حتى للتحية في الثواني
    # الأولى): الكود السابق كان ينفّذ ``db.get(User)`` على Supabase عند كل اتصال.
    # تحت ضغط Supabase (استنفاد pool / بطء / انقطاع) كان يفشل → إغلاق 1013 →
    # الواجهة تُعيد الاتصال → يفشل ثانية → تأرجح مستمر؛ الاتصال لا يثبت أبداً
    # فلا تُعالَج حتى رسالة «السلام عليكم». الهوية (المعرّف + is_admin) موجودة
    # في الـ JWT الموقّع، فلا داعي لقاعدة البيانات لإنشاء الاتصال. عمل قاعدة
    # البيانات يحدث لكل دور داخل جلسته الخاصة مع معالجة أخطائه دون إسقاط الاتصال.
    try:
        claims = decode_token_payload(token, get_settings().SECRET_KEY)
        user_id = int(claims["sub"])
    except (HTTPException, KeyError, TypeError, ValueError):
        await websocket.accept(subprotocol=selected_protocol)
        await websocket.send_json(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {
                        "details": "Invalid or expired token. Please log in again.",
                        "code": "WS_AUTH_INVALID",
                        "status_code": 4401,
                    },
                }
            )
        )
        await websocket.close(code=4401)
        return

    # ISS-103 (D-WS-CONN-002): is_admin يُشتق من claim ``is_admin`` صراحةً أو من
    # دور ``ADMIN`` ضمن ``roles`` (رمز الوصول الحقيقي يحمل ``roles`` لا ``is_admin``).
    # بدون اشتقاق الدور كان كل توكن حقيقي يُعطي is_admin=False → دردشة الإدمن
    # مرفوضة دائماً (admin.py: "Standard accounts must use the customer chat endpoint").
    _claim_roles = claims.get("roles") or []
    is_admin_claim = bool(claims.get("is_admin", False)) or (
        ADMIN_ROLE in _claim_roles if isinstance(_claim_roles, list) else False
    )
    actor = WsActor(id=user_id, is_admin=is_admin_claim)

    await websocket.accept(subprotocol=selected_protocol)

    if actor.is_admin:
        await websocket.send_json(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {
                        "details": "Admin accounts must use the admin chat endpoint.",
                        "status_code": 403,
                    },
                }
            )
        )
        await websocket.close(code=4403)
        return

    # D-096 (2026-05-28): قفل تسلسلي للـ WebSocket sends.
    # يُمنع التزامن بين BKT background task و stream_and_forward و
    # _emit_terminal_frames و handle_control_message.
    # السبب: Starlette WebSocket.send_json لا يضمن coroutine-safety
    # عند استدعاءات متزامنة → corruption → silent close → kick.
    send_lock = asyncio.Lock()

    # D-WS-FLAP-003 (2026-05-26): primer event — يُرسَل فور الـ accept لإجبار
    # كل الـ proxies على المسار (server.js, Codespaces edge, mobile carrier-NAT)
    # على فتح/الاحتفاظ بـ session نشط بدلاً من idle-timeout سريع.
    # الواجهة تتجاهل النوع غير المعروف (useAgentSocket لا يعالج "session_ready").
    try:
        async with send_lock:
            await websocket.send_json(
                {
                    "type": "session_ready",
                    "payload": {
                        "user_id": actor.id,
                        "ts": datetime.now(UTC).isoformat(),
                    },
                }
            )
    except Exception as exc:
        # primer non-fatal — لو فشل، السبب أن الـ socket أُغلق فوراً.
        logger.debug("customer_chat.primer_failed: %s", exc)

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                # D-ISS-092: receive_json() يُطلق RuntimeError عند إغلاق Codespaces proxy
                # للاتصال بشكل مفاجئ. نُعيد الـ raise ليُمسكه الـ except الخارجي بشكل نظيف.
                raise

            # D-WS-FLAP-002 (ISS-WS-FLAP-002): معالج heartbeat موحَّد كـ Skill.
            # رسائل التحكم (ping/heartbeat/noop) تُعالَج هنا قبل أي محاولة
            # لاعتبار الحمولة سؤالاً. بدون هذا الفحص، ping يُعاد إليه «Question is
            # required» بدلاً من pong → timeout بعد 10s → close(1001) → flapping.
            if await handle_control_message(websocket, payload, send_lock=send_lock):
                continue

            request_id_value = payload.get("client_request_id")
            client_request_id = (
                str(request_id_value).strip() if request_id_value is not None else None
            )
            if client_request_id == "":
                client_request_id = None
            stream_request_id = client_request_id or str(uuid.uuid4())

            question = str(payload.get("question", "")).replace("\x00", "").strip()
            if not question:
                await _locked_send_json(
                    websocket,
                    send_lock,
                    _bind_stream_metadata(
                        normalize_streaming_event(
                            {
                                "type": "error",
                                "payload": {"details": "Question is required."},
                            }
                        ),
                        None,
                        stream_request_id,
                    ),
                )
                continue

            mission_type = payload.get("mission_type")
            metadata: dict[str, object] = {}
            if mission_type:
                metadata["mission_type"] = mission_type
            client_context_messages = _extract_client_context_messages(payload)
            if client_context_messages:
                metadata["client_context_messages"] = client_context_messages

            original_conversation_id = payload.get("conversation_id")
            local_conversation_id: int | None = None
            history_messages: list[dict[str, str]] = []

            turn_span = open_ws_turn(
                user_id=actor.id,
                conversation_id=None,
                is_admin=False,
                question=question,
                request_id=stream_request_id,
            )

            try:
                async with async_session_factory() as db:
                    persistence_service = CustomerChatBoundaryService(db)
                    local_conversation = await persistence_service.get_or_create_conversation(
                        actor,
                        question,
                        original_conversation_id,
                    )
                    local_conversation_id = local_conversation.id
                    turn_span.set_conversation_id(local_conversation_id)
                    logger.info(
                        "[WRITE_DECISION] conversation_id=%s role=user action=WRITE",
                        local_conversation_id,
                    )
                    await persistence_service.save_message(
                        local_conversation_id,
                        MessageRole.USER,
                        question,
                    )
                    history_messages = await persistence_service.get_chat_history(
                        local_conversation_id,
                        limit=50,
                    )
                    history_messages = _merge_history_with_client_context(
                        history_messages,
                        client_context_messages,
                    )
                await _locked_send_json(
                    websocket,
                    send_lock,
                    normalize_streaming_event(
                        {
                            "type": "conversation_init",
                            "payload": {
                                "conversation_id": local_conversation_id,
                                "request_id": stream_request_id,
                            },
                        }
                    ),
                )
            except HTTPException as http_exc:
                await _locked_send_json(
                    websocket,
                    send_lock,
                    _bind_stream_metadata(
                        normalize_streaming_event(
                            {
                                "type": "error",
                                "payload": {
                                    "details": str(http_exc.detail),
                                    "status_code": http_exc.status_code,
                                },
                            }
                        ),
                        local_conversation_id,
                        stream_request_id,
                    ),
                )
                turn_span.set_terminal("error")
                close_ws_turn(turn_span, status="ERROR")
                continue
            except Exception as exc:
                logger.error(
                    f"Failed to persist customer user message locally: {exc}",
                    exc_info=True,
                )
                await _locked_send_json(
                    websocket,
                    send_lock,
                    _bind_stream_metadata(
                        normalize_streaming_event(
                            {
                                "type": "error",
                                "payload": {
                                    "details": "Failed to save your message locally.",
                                    "status_code": 500,
                                },
                            }
                        ),
                        local_conversation_id,
                        stream_request_id,
                    ),
                )
                turn_span.set_terminal("error")
                close_ws_turn(turn_span, status="ERROR")
                continue

            # ─────────────────────────────────────────────────────────────────
            # BKT Runtime Injection (Protocol V6.0): قيّم التفاعل، خزّنه في
            # student_bkt_analytics، وابنِ بطاقتَي التتبّع. غير حرج — أي فشل لا
            # يكسر مسار المحادثة (try/except معزول، جلسة DB مستقلة).
            #
            # D-WS-FLAP-001: التقييم يُشغَّل كـ background task (DB متزامن) فلا
            # يُحجب بدء البثّ. RUF006: نحتفظ بمرجع الـ task لمنع GC المبكر.
            # D-118: الإصدار لم يَعُد هنا — `_evaluate_bkt_cards` يُرجِع الحمولات
            # فقط (بلا بثّ/حفظ)، والمنسّق يُصدِرها بعد الإطار النهائي للمحتوى كي
            # لا تُشظّي نص التمرين أثناء البثّ (كانت تُقطّعه لفقاعات مكسورة).
            # ─────────────────────────────────────────────────────────────────
            _bkt_task = asyncio.create_task(
                _evaluate_bkt_cards(
                    user_id=actor.id,
                    conversation_id=local_conversation_id,
                    question=question,
                    history_messages=history_messages,
                )
            )
            _bkt_task.add_done_callback(
                lambda t: (
                    logger.debug("bkt_task_done err=%s", t.exception()) if t.exception() else None
                )
            )

            complete_ai_response = ""
            assistant_message_persisted = False
            orchestrator_persisted = False
            pending_terminal_event: dict[str, object] | None = None
            stream_task: asyncio.Task[None] | None = None
            stream_error: HTTPException | Exception | None = None
            # ISS-106 (D-WS-CARD-PERSIST-001): اجمع كل بطاقات ui_component المستقلة
            # المبثوثة خلال الدور (شجرة احتمالات، بطاقة شرح، قصة تمرين...) لحفظها
            # كصفوف مستقلة فتبقى بعد إعادة الدخول.
            captured_ui_components: list[dict[str, object]] = []

            # D-104/D-114: صورة المتعلم تقود عمق التدريس — التوجيه التربوي التكيفي
            # يُقرأ من إتقان BKT (fail-open، سقف 2s، جلسة DB معزولة) ويُمرَّر عبر
            # context ليُسبق في سؤال الـ LLM (orchestrator + fallbacks). support_level
            # يعبر السلسلة كاملةً ويحكم بوّابة المثال المحلول + إعفاء الحجب.
            pedagogy_snapshot = await _build_pedagogy_directive(
                user_id=actor.id,
                question=question,
                history_messages=history_messages,
            )
            pedagogy_directive = pedagogy_snapshot.directive_text
            support_level = pedagogy_snapshot.support_level

            # D-115: التوليد التعليمي يحدث حصراً في الـ orchestrator (السلطة الوحيدة).
            # support_level يُمرَّر ليحكم عمق التلميح السقراطي هناك (لا مثال مكشوف
            # ولا توجيه LLM محقون — يَعكِس D-114 الذي تسبّب بالغارباج).

            try:

                async def stream_and_forward(
                    q=question,
                    lc_id=local_conversation_id,
                    meta=metadata,
                    history=history_messages,
                    request_id=stream_request_id,
                    captured=captured_ui_components,
                    pedagogy=pedagogy_directive,
                    sup_level=support_level,
                ) -> None:
                    nonlocal pending_terminal_event
                    nonlocal complete_ai_response
                    nonlocal orchestrator_persisted
                    async for event in orchestrator_client.chat_with_agent(
                        question=q,
                        user_id=actor.id,
                        conversation_id=lc_id,
                        history_messages=history,
                        context={
                            "chat_scope": "customer",
                            "metadata": meta,
                            "compatibility_facade": True,
                            "pedagogy_directive": pedagogy,
                            "support_level": sup_level,
                        },
                    ):
                        # D-WS-FLAP-001: abort stream if client disconnected mid-turn.
                        # Without this check, send_json raises RuntimeError which
                        # escapes the task and corrupts the outer finally block state.
                        if not _ws_is_connected(websocket):
                            logger.info(
                                "customer_chat.stream_aborted: client disconnected mid-stream "
                                "(conversation_id=%s)",
                                lc_id,
                            )
                            return

                        normalized_event = normalize_streaming_event(event)

                        # ISS-STREAM-001: تصفية أحداث noop (أحداث غير معروفة من orchestrator)
                        if normalized_event.get("type") == "noop":
                            continue

                        # Prevent "Split-Brain" DB FK violation:
                        # Intercept Orchestrator's conversation_init and rewrite/strip conversation_id
                        # so the local frontend doesn't overwrite its local sequence with Orchestrator's sequence.
                        if normalized_event.get("type") == "conversation_init" and isinstance(
                            normalized_event.get("payload"), dict
                        ):
                            if lc_id is not None:
                                # Rewrite to the established local sequence
                                normalized_event["payload"]["conversation_id"] = lc_id
                            else:
                                # Strip it to avoid overwriting local state with a foreign ID
                                normalized_event["payload"].pop("conversation_id", None)

                        event_type = normalized_event.get("type")
                        if event_type in {"complete", "assistant_final"}:
                            # Detect orchestrator persistence signal
                            if normalized_event.get("persisted") is True:
                                orchestrator_persisted = True
                            pending_terminal_event = _bind_stream_metadata(
                                normalized_event, lc_id, request_id
                            )
                        else:
                            # ISS-106 (D-WS-CARD-PERSIST-001): اجمع بطاقات ui_component
                            # المستقلة لحفظها لاحقاً (تبقى بعد إعادة الدخول).
                            if event_type == "ui_component" and isinstance(
                                normalized_event.get("payload"), dict
                            ):
                                captured.append(dict(normalized_event["payload"]))
                            # D-115: مُطهّر العرض المُصفّح على كل delta نصّي — شبكة
                            # أمان فوق تنظيف الـ orchestrator (لا ⟦⟧ ولا تعليمات مُسرَّبة).
                            display_event = normalized_event
                            if _is_text_event(normalized_event) and isinstance(
                                normalized_event.get("payload"), dict
                            ):
                                _disp = normalized_event["payload"].get("content")
                                if isinstance(_disp, str) and _disp:
                                    display_event = {
                                        **normalized_event,
                                        "payload": {
                                            **normalized_event["payload"],
                                            "content": _strip_display_garbage(_disp),
                                        },
                                    }
                            # D-096: send_lock يمنع التزامن مع BKT task
                            await _locked_send_json(
                                websocket,
                                send_lock,
                                _bind_stream_metadata(display_event, lc_id, request_id),
                            )

                        if _is_text_event(normalized_event) and isinstance(
                            normalized_event.get("payload"), dict
                        ):
                            chunk_text = normalized_event["payload"].get("content")
                            if isinstance(chunk_text, str) and chunk_text:
                                # D-115: التراكم النظيف (لا غارباج في النسخة المحفوظة).
                                complete_ai_response += _strip_display_garbage(chunk_text)

                stream_task = asyncio.create_task(stream_and_forward())
                # ISS-098 (D-WS-FLAP-005): keepalive متزامن يمنع false
                # heartbeat-timeout على العميل أثناء الأدوار الطويلة.
                keepalive_task = asyncio.create_task(_run_turn_keepalive(websocket, send_lock))
                try:
                    await stream_task
                finally:
                    keepalive_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await keepalive_task

            except HTTPException as http_exc:
                stream_error = http_exc
                logger.error(
                    f"HTTPException in compatibility facade stream: {http_exc}", exc_info=True
                )
            except Exception as exc:
                stream_error = exc
                logger.error(f"Error in compatibility facade stream: {exc}", exc_info=True)
                # D-096: locked send + state check
                if (
                    not isinstance(exc, WebSocketDisconnect)
                    and websocket.client_state == WebSocketState.CONNECTED
                ):
                    try:
                        await _locked_send_json(
                            websocket,
                            send_lock,
                            normalize_streaming_event(
                                {
                                    "type": "error",
                                    "payload": {"details": str(exc), "status_code": 500},
                                }
                            ),
                        )
                    except (WebSocketDisconnect, RuntimeError) as _send_err:
                        logger.debug(
                            "customer_chat.error_send_failed: %s", type(_send_err).__name__
                        )
            finally:
                if stream_task is not None and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        logger.info("Cancelled customer stream task after disconnect/finalization")

                # ── Persistence decision (single-writer coordination) ──
                # Monolith owns the message. If Orchestrator already persisted
                # (signaled via persisted=True on terminal event), skip local write;
                # otherwise fail-safe write. Absence of signal is treated as failure.
                # D-086 (V46.0): تطبيق OutputFirewall على الإجابة المكتملة
                # قبل الحفظ في DB — يضمن نقاء القناة B في السجل الدائم.
                if complete_ai_response:
                    complete_ai_response = _apply_complete_response_firewall(complete_ai_response)
                    # D-113/D-115: حجب الإجابة النهائية على النسخة المحفوظة — شبكة أمان
                    # حتمية ضد كشف الجواب (لا كشف في التدفّق العادي؛ الكشف لوضع مراجعة منفصل).
                    complete_ai_response = _apply_final_answer_redaction(
                        complete_ai_response, support_level
                    )

                if (
                    not assistant_message_persisted
                    and complete_ai_response
                    and local_conversation_id is not None
                ):
                    if orchestrator_persisted:
                        logger.info(
                            "[WRITE_DECISION] conversation_id=%s role=assistant "
                            "orchestrator_persisted=True action=SKIP",
                            local_conversation_id,
                        )
                        assistant_message_persisted = True
                    else:
                        logger.warning(
                            "[WRITE_DECISION] conversation_id=%s role=assistant "
                            "orchestrator_persisted=False action=WRITE (Fail-Safe) "
                            "- Absence of signal treated as failure.",
                            local_conversation_id,
                        )
                        # ISS-106 (D-WS-CARD-PERSIST-001): البطاقة الرياضية تُبنى من
                        # النص المكتمل وتُرفق برسالة المساعد لتبقى بعد إعادة الدخول.
                        _assistant_card = _try_build_math_ui_component(
                            complete_ai_response.replace("\x00", "")
                        )
                        for _attempt in range(2):
                            try:
                                async with async_session_factory() as db:
                                    persistence_service = CustomerChatBoundaryService(db)
                                    await persistence_service.save_message(
                                        conversation_id=local_conversation_id,
                                        role=MessageRole.ASSISTANT,
                                        content=complete_ai_response.replace("\x00", ""),
                                        ui_component=_assistant_card,
                                    )
                                    assistant_message_persisted = True
                                    logger.info(
                                        "[DATA_LOSS_PREVENTED] Fallback persistence succeeded."
                                    )
                                break
                            except Exception as persistence_exc:
                                logger.error(
                                    (
                                        "Failed to persist customer assistant message locally "
                                        f"for conversation {local_conversation_id} "
                                        f"(attempt {_attempt + 1}/2): {persistence_exc}"
                                    ),
                                    exc_info=True,
                                )

                        if not assistant_message_persisted:
                            logger.error(
                                "[CRITICAL_DATA_LOSS] Fallback persistence completely failed for "
                                f"conversation {local_conversation_id}."
                            )

                # ── Persist standalone generative-UI cards (ISS-106) ──
                # كل بطاقة ui_component مستقلة بُثَّت خلال الدور (شجرة احتمالات، قصة
                # تمرين، بطاقة شرح...) تُحفظ كصف مساعد content="" لتُصيَّر من التاريخ
                # بعد إعادة الدخول. غير حرج: أي فشل يُسجَّل ولا يكسر إنهاء الدور.
                if captured_ui_components and local_conversation_id is not None:
                    await _persist_ui_component_cards(
                        conversation_id=local_conversation_id,
                        cards=captured_ui_components,
                    )

                # ── Guaranteed terminal frame ──
                # Exactly one terminal event (assistant_final or error) per turn,
                # so the UI never hangs. `persisted` is emitted only after a real save.
                # D-WS-FLAP-001: wrapped in try/except — if the client disconnected
                # mid-stream, send_json raises RuntimeError/WebSocketDisconnect.
                # Without this guard the exception escapes finally, the loop retries
                # receive_json on a dead socket, and the client sees a flapping pattern.
                try:
                    await _emit_terminal_frames(
                        websocket=websocket,
                        send_lock=send_lock,  # D-096
                        pending_terminal_event=pending_terminal_event,
                        assistant_message_persisted=assistant_message_persisted,
                        complete_ai_response=complete_ai_response,
                        stream_error=stream_error,
                        local_conversation_id=local_conversation_id,
                        stream_request_id=stream_request_id,
                    )
                except (WebSocketDisconnect, RuntimeError) as _ws_close_err:
                    logger.info(
                        "customer_chat.terminal_frame_skipped: client already disconnected "
                        "(conversation_id=%s err=%s)",
                        local_conversation_id,
                        type(_ws_close_err).__name__,
                    )

                # ── D-118: بطاقات التتبّع تُصدَر بعد الإطار النهائي للمحتوى ──
                # كانت تُبثّ متزامنةً (asyncio.create_task) فتهبط بين deltas
                # وتُشظّي نص التمرين لفقاعات مكسورة. الآن: انتظر التقييم (انتهى
                # أثناء البثّ → فوري)، احفظ ثم أصدِر البطاقتين أسفل المحتوى — مرة
                # نظيفة، بترتيب live/reload موحَّد (محتوى → مرئي → تتبّع). معزول
                # كلياً: لا يكسر إنهاء الدور (D-074: BKT لا يكسر الدردشة أبداً).
                _bkt_cards: list[dict[str, object]] = []
                try:
                    _bkt_cards = await _bkt_task
                except Exception as _bkt_exc:
                    logger.debug("bkt_cards_await_failed: %s", _bkt_exc)
                if _bkt_cards:
                    if local_conversation_id is not None:
                        with contextlib.suppress(Exception):
                            await _persist_ui_component_cards(
                                conversation_id=local_conversation_id,
                                cards=[dict(c) for c in _bkt_cards],
                            )
                    for _card in _bkt_cards:
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        try:
                            await _locked_send_json(
                                websocket,
                                send_lock,  # D-096
                                _bind_stream_metadata(
                                    {"type": "ui_component", "payload": _card},
                                    local_conversation_id,
                                    stream_request_id,
                                ),
                            )
                        except (WebSocketDisconnect, RuntimeError):
                            break

                # Close path-aware span exactly once per turn — final event type
                # mirrors what `_emit_terminal_frames` actually sent.
                if assistant_message_persisted:
                    turn_span.set_terminal("assistant_final")
                    close_ws_turn(turn_span, status="OK")
                else:
                    turn_span.set_terminal("error")
                    close_ws_turn(turn_span, status="ERROR")

    except (WebSocketDisconnect, RuntimeError) as exc:
        # RuntimeError: "WebSocket is not connected" — يحدث عندما يُغلق Codespaces proxy
        # الاتصال بشكل مفاجئ قبل أن يُكمل receive_json(). بدون هذا الـ catch،
        # الـ exception يهرب إلى ASGI layer ويُسبب "Exception in ASGI application"
        # مما يُعيد تشغيل الـ connection loop في الـ frontend → kick-to-login flapping.
        if isinstance(exc, RuntimeError):
            logger.info("customer_chat.ws_runtime_disconnect: %s", exc)
        else:
            logger.info("Customer WebSocket disconnected")


@router.get(
    "/latest",
    summary="استرجاع آخر محادثة",
    response_model=CustomerConversationDetails | None,
)
async def get_latest_chat(
    actor: User = Depends(get_actor_user),
    service: CustomerChatBoundaryService = Depends(get_customer_service),
) -> CustomerConversationDetails | None:
    conversation_data = await service.get_latest_conversation_details(actor)
    if not conversation_data:
        return None
    return CustomerConversationDetails.model_validate(conversation_data)


@router.get(
    "/conversations",
    summary="سرد المحادثات",
    response_model=list[CustomerConversationSummary],
)
async def list_conversations(
    actor: User = Depends(get_actor_user),
    service: CustomerChatBoundaryService = Depends(get_customer_service),
) -> list[CustomerConversationSummary]:
    results = await service.list_user_conversations(actor)
    return [CustomerConversationSummary.model_validate(r) for r in results]


@router.get(
    "/conversations/{conversation_id}",
    summary="تفاصيل محادثة",
    response_model=CustomerConversationDetails,
    description="استرجاع تفاصيل محادثة محددة.",
    operation_id="chatConversationGet",
)
async def get_conversation(
    conversation_id: int,
    actor: User = Depends(get_actor_user),
    service: CustomerChatBoundaryService = Depends(get_customer_service),
) -> CustomerConversationDetails:
    data = await service.get_conversation_details(actor, conversation_id)
    return CustomerConversationDetails.model_validate(data)
