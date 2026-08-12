"""آلة دور الدردشة على WebSocket — نسخةٌ واحدة لمسارَي العميل والإدمن (ISS-155).

كانت هذه الحلقة مكتوبةً **مرّتين** في `routes.py` (301 سطراً، ~120 منها متطابقة
بالبايت). الفروق الستّة بين المسارين مُرمَّزة في `chat_ws_scope.ChatWsScope`، ووثيقتها
هناك — فتُقرأ إجابة «بمَ يختلفان؟» بلا قراءة الآلة.

## الفصل بالمسؤولية قبل أوّل قياس

درس D-237/ADR-009 (البند ٣): أوّل استخراجٍ هناك نقل المولّدَين سليمَين، فقاست
البوّابة `cc 35` و`عمق 11` في الوحدة الجديدة — **دالّةٌ إلهية استُبدلت بوحدةٍ
إلهية**. ولذلك تُوزَّع المسؤوليات هنا على ثلاث وحدات: `chat_ws_scope` (ما يختلف) ·
`chat_turn_context` (قراءة الحمولة) · وهذه (تسلسل الدور).

وقد صرخت البوّابة فعلاً أثناء هذا العمل: أوّل صياغةٍ جمعت الوصف مع الآلة فقاست
`loc 302 > 300` كـ«وافدٍ جديد». فُصلت المسؤوليتان بدل ضغط الأسطر — **الرقم يُخفَّض
بالبنية لا بالضغط** (D-237 · البند ٩).

## البرهان

`tests/microservices/fixtures/chat_ws_transcript_golden.json` يُجمّد إطارات المقبس
ووسائط المحرّك لعشرة سيناريوهات × نطاقَين، وقد وُلِّد **قبل** هذا النقل. بقاؤه بلا
تغيّر بايتٍ واحد **هو** برهان التكافؤ. ويحرس ظهورَ فرقٍ **سابع**
`test_the_twins_differ_only_in_the_six_measured_things`.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from microservices.orchestrator_service.src.core.database import async_session_factory

from .chat_stream_engine import _stream_chat_langgraph
from .chat_turn_context import (
    _apply_mission_type,
    _coerce_client_context,
    _extract_chat_objective,
    _hydrate_history,
)
from .chat_types import ChatRunContext
from .chat_ws_scope import ChatWsScope, WsTurnBundle, WsTurnState
from .conversation_store import _ensure_conversation
from .identity_access import (
    _build_conversation_thread_id,
    _emit_identity_diagnostic_log,
    _resolve_effective_conversation_id,
    _resolve_session_id_from_incoming,
)

logger = logging.getLogger(__name__)


async def _read_turn(websocket: WebSocket) -> tuple[dict[str, object], str] | None:
    """يقرأ رسالةً ويعيد `(الحمولة, الهدف)` — أو `None` بعد بثّ إطار خطأٍ صريح.

    يُعيد **الزوج** بدل إعادة حساب الهدف لاحقاً: الأصل يحسبه مرّةً واحدة، و«نقيّة
    اليوم» ليست عقداً. والمقبس يبقى مفتوحاً في الحالتين — الخطأ لا ينهي الجلسة.
    """
    incoming = await websocket.receive_json()
    if not isinstance(incoming, dict):
        await websocket.send_json({"status": "error", "message": "invalid payload"})
        return None
    objective = _extract_chat_objective(incoming)
    if objective is None:
        await websocket.send_json({"status": "error", "message": "question/objective required"})
        return None
    return incoming, objective


def _resolve_turn_conversation_id(*, bundle: WsTurnBundle, incoming: dict[str, object]) -> object:
    """يحسم مُعرّف المحادثة لهذا الدور، ويُبطِل الخيط اللاصق عند تبديل المحادثة."""
    requested_conversation_id = incoming.get("conversation_id")

    logger.info(
        "[CONV_LIFECYCLE] stage=ws_received role=%s user=%s conv_id=%s type=%s",
        bundle.scope.name,
        bundle.user_id,
        requested_conversation_id,
        type(requested_conversation_id).__name__,
    )
    conversation_id = _resolve_effective_conversation_id(
        incoming_value=requested_conversation_id,
        sticky_value=bundle.state.sticky_conversation_id,
    )
    if (
        requested_conversation_id is not None
        and requested_conversation_id != bundle.state.sticky_conversation_id
    ):
        bundle.state.sticky_thread_id = None
    logger.info(
        "[CONV_LIFECYCLE] stage=parsed role=%s user=%s conv_id=%s type=%s",
        bundle.scope.name,
        bundle.user_id,
        conversation_id,
        type(conversation_id).__name__,
    )
    return conversation_id


async def _ensure_turn_conversation(
    websocket: WebSocket,
    *,
    bundle: WsTurnBundle,
    conversation_id: object,
) -> tuple[int, list[dict[str, str]]] | None:
    """يضمن المحادثة ويحدّث الحالة اللاصقة — أو يبثّ خطأً صريحاً ويعيد `None`.

    `bundle` يجمّع ما يسافر معاً في كلّ نداءات الآلة (سابقة D-237 ·
    `TurnIdentity`)، ويبقى المقبس منفصلاً لأنه ناقل الخطأ، و`conversation_id`
    منفصلاً لأنه نتيجة مرحلة التحليل لا خاصية الدور.
    """
    try:
        logger.info(
            f"ORCHESTRATOR received | chat_scope={bundle.scope.name} | role={bundle.user_id}"
        )
        logger.info(
            "[CONV_LIFECYCLE] stage=ensure_entry role=%s user=%s conv_id=%s",
            bundle.scope.name,
            bundle.user_id,
            conversation_id,
        )
        async with async_session_factory() as session:
            resolved_id, history_messages = await _ensure_conversation(
                session=session,
                chat_scope=bundle.scope.name,
                user_id=bundle.user_id,
                question=bundle.objective,
                requested_conversation_id=conversation_id,
            )
        logger.info(
            "[CONV_LIFECYCLE] stage=ensure_exit role=%s user=%s conv_id=%s msg_count=%s",
            bundle.scope.name,
            bundle.user_id,
            resolved_id,
            len(history_messages),
        )
        bundle.state.sticky_conversation_id = resolved_id
        bundle.state.sticky_thread_id = _build_conversation_thread_id(bundle.user_id, resolved_id)
    except HTTPException as error:
        await websocket.send_json({"type": "assistant_error", "payload": {"content": error.detail}})
        return None
    return resolved_id, history_messages


def _build_turn_context(
    *,
    bundle: WsTurnBundle,
    incoming: dict[str, object],
    conversation_id: int,
) -> ChatRunContext:
    """يبني سياق الدور ويُصدِر سجلّ تشخيص الهويّة."""
    context: ChatRunContext = _coerce_client_context(incoming.get("context"))
    _apply_mission_type(context, incoming)
    context["conversation_id"] = conversation_id
    context["user_id"] = bundle.user_id
    if bundle.state.sticky_thread_id:
        context["thread_id"] = bundle.state.sticky_thread_id
    _emit_identity_diagnostic_log(
        route_name=bundle.scope.route_name,
        conversation_id=conversation_id,
        thread_id=bundle.state.sticky_thread_id,
        session_id=_resolve_session_id_from_incoming(incoming),
    )
    return context


async def _run_turn(
    websocket: WebSocket,
    *,
    scope: ChatWsScope,
    state: WsTurnState,
    user_id: int,
    admin_payload: dict[str, object] | None,
) -> None:
    """ينفّذ دوراً واحداً كاملاً. يعود مبكّراً حين يُبَثّ إطار خطأٍ — والمقبس يبقى حيّاً."""
    turn = await _read_turn(websocket)
    if turn is None:
        return
    incoming, objective = turn

    bundle = WsTurnBundle(scope=scope, state=state, user_id=user_id, objective=objective)

    conversation_id = _resolve_turn_conversation_id(bundle=bundle, incoming=incoming)
    ensured = await _ensure_turn_conversation(
        websocket, bundle=bundle, conversation_id=conversation_id
    )
    if ensured is None:
        return
    resolved_id, history_messages = ensured

    await websocket.send_json(
        {"type": "conversation_init", "payload": {"conversation_id": resolved_id}}
    )

    context = _build_turn_context(bundle=bundle, incoming=incoming, conversation_id=resolved_id)

    await _stream_chat_langgraph(
        websocket,
        objective=objective,
        context=context,
        chat_scope=scope.name,
        conversation_id=resolved_id,
        app_graph=getattr(websocket.app.state, "app_graph", None),
        admin_payload=admin_payload,
        history_messages=_hydrate_history(history_messages, incoming),
    )
    logger.info(
        "[CONV_LIFECYCLE] stage=response_sent role=%s user=%s conv_id=%s",
        scope.name,
        user_id,
        resolved_id,
    )


async def serve_chat_ws(
    websocket: WebSocket,
    *,
    scope: ChatWsScope,
    user_id: int,
    admin_payload: dict[str, object] | None = None,
) -> None:
    """يخدم مقبساً مُصادَقاً ومقبولاً حتى ينقطع.

    المصادقة والتفويض و`accept` تبقى في الغلاف داخل `routes.py` — فهي الفرقان
    الأوّل والثاني بين التوأمين، وقاعدة الإقامة (D-168) تُبقي المُعالِجات المُزخرَفة
    في ملفّها على أيّ حال.
    """
    state = WsTurnState()
    try:
        while True:
            await _run_turn(
                websocket,
                scope=scope,
                state=state,
                user_id=user_id,
                admin_payload=admin_payload,
            )
    except WebSocketDisconnect:
        logger.info(scope.disconnect_message)
