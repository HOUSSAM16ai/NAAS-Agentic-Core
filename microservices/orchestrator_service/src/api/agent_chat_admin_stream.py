"""مولّد البثّ الإداري لـ`/agent/chat` — D-168 Slice A6.

مُستخرَجة من مُغلَقة `_admin_stream` (`routes.py:942-1128`) ثمّ **مُفكَّكة**: النقل
وحده كان ينقل التعقيد لا يزيله (قاست البوّابة الدالّة المنقولة عند cc=35 وعمق=11،
فردّتها — «استبدال دالّةٍ إلهية بوحدةٍ إلهية ليس تحسيناً»).

المسؤوليات صارت أربعاً، كلٌّ قابلة للاختبار وحدها:

| الدالّة | المسؤولية |
|---|---|
| `_is_reportable_node` | أيّ عُقَد LangGraph تُعلَن للعميل |
| `_stream_delta_content` | استخراج القطعة النصّية (D-047 · D-048) |
| `_final_response_from_chain_end` | التقاط الردّ النهائي من حالة الرسم |
| `_finalise_admin_turn` | الحفظ + الإطار النهائي (§6.5) |

تعتمد على الأشقاء فقط — لا تستورد `routes` (طبقاتٌ باتجاه واحد، D-168).

## ما يجب ألّا يتغيّر هنا

- **بحث `admin_app` داخل `try`**: إن غاب الرسم تُرفَع `RuntimeError` فتلتقطها
  المِظلّة وتُبَثّ إطار خطأ آمن. رفعُها **قبل** المولّد يحوّل الحالة إلى 500 بلا
  إطار — أي فشلٌ صامت للعميل (§0).
- **`persisted` على الإطار النهائي** — عقد §6.5 (كاتبٌ واحد). ⚠️ يُسقطه
  `StreamFrame` اليوم قبل بلوغ السلك (ISS-153): عطبٌ **موثَّق ولم يُصلَح في هذه
  الجولة**، والتوثيق هنا كي لا يُقرأ الغياب تصميماً.
- **قمع التكرار (D-047)**: بعد بثّ القطع رمزاً رمزاً يحمل الإطار النهائي `""` لأن
  المتصفّح يجمعها عبر `mergeAssistantContent`.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from microservices.orchestrator_service.src.core.database import async_session_factory

from .chat_context import _augment_ambiguous_objective, _detect_checkpoint_state
from .conversation_store import _ensure_conversation, _persist_assistant_message
from .identity_access import _merge_admin_inputs, _resolve_thread_id, _safe_assistant_error
from .stream_serialization import _extract_human_readable_response, _serialize_stream_frame

logger = logging.getLogger(__name__)

_PHASE_BY_EVENT = {"on_chain_start": "phase_start", "on_chain_end": "phase_completed"}


def _is_reportable_node(node_name: str) -> bool:
    """عُقَد التنسيق الداخلية (`__*` و`LangGraph`) لا تُعلَن للعميل."""
    return bool(node_name) and not node_name.startswith("__") and node_name != "LangGraph"


def _stream_delta_content(event: dict[str, object], evt_type: str) -> str | None:
    """يستخرج القطعة النصّية من مساري البثّ الرمزي — D-047 و D-048."""
    if evt_type == "on_chat_model_stream":
        # D-047: token-level streaming when nodes use LangChain ChatOpenAI
        chunk = event.get("data", {}).get("chunk")
        content = None if chunk is None else getattr(chunk, "content", None)
    elif evt_type == "on_custom_event":
        # D-048: token-level streaming from DSPy/raw-OpenAI nodes via stream_writer
        data = event.get("data")
        is_delta = isinstance(data, dict) and data.get("chunk_type") == "assistant_delta"
        content = data.get("content") if is_delta else None
    else:
        return None
    return content if isinstance(content, str) and content else None


def _final_response_from_chain_end(event: dict[str, object], current: object) -> object:
    """يلتقط `final_response` من إغلاق الرسم — ويُبقي القائم إن لم يحمل الحدث ردّاً."""
    node_name = event.get("name", "")
    if node_name and node_name != "LangGraph":
        return current
    output_data = event["data"].get("output", {})
    if not (output_data and isinstance(output_data, dict)):
        return current
    if "final_response" in output_data:
        return output_data["final_response"]
    if output_data.get("messages"):
        last_msg = output_data["messages"][-1]
        if hasattr(last_msg, "content"):
            return last_msg.content
    return current


async def _prepare_admin_run(
    *,
    question: str,
    user_id: int,
    conversation_id: int | None,
    history_messages: list[dict[str, str]],
    admin_payload: dict[str, object],
    request_context: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """يبني مدخلات الرسم الإداري وإعداد التشغيل (`thread_id` + أثر التتبّع)."""
    # Augment the objective for explicit context before sending to LangGraph
    prepared_objective = _augment_ambiguous_objective(question, history_messages)

    # ⚠️ شريحةٌ ميتة مُبقاةٌ عمداً في هذه الخطوة (كانت `routes.py:963-974`): النتيجة
    # لا يقرأها أحد، لكنّ حذفها تغييرُ سلوكٍ (جولة قاعدة بيانات أقلّ لكلّ طلب) فيُفرَد
    # بالتزامٍ مستقلّ قابل للتراجع بعد إثبات التكافؤ. النقل يبقى حرفياً.
    conversation_id_fallback = conversation_id if conversation_id else str(uuid.uuid4())
    _dead_thread_id = _resolve_thread_id(
        {"user_id": user_id, "conversation_id": conversation_id},
        fallback_conversation_id=str(conversation_id_fallback),
    )
    _checkpointer_available, _checkpoint_has_state = await _detect_checkpoint_state(_dead_thread_id)

    # `query` هو ما تقرأه عقدة الإدارة لاختيار الأداة:
    # graph/admin.py:128 `resolve_tool_deterministic(state.get("query", ""))`.
    # كان غائباً هنا وحده، فكان كلّ سؤالٍ إداري على هذا المسار يُحلّ أداته على
    # سلسلةٍ فارغة. مسار StateGraph يضعه صراحةً (chat_stream_engine.py:491).
    admin_inputs = _merge_admin_inputs(
        {
            "messages": [{"role": "user", "content": prepared_objective}],
            "query": prepared_objective,
        },
        admin_payload,
    )

    effective_conversation_id = conversation_id if conversation_id else str(uuid.uuid4())
    thread_id = _resolve_thread_id(
        {"user_id": user_id, "conversation_id": conversation_id},
        fallback_conversation_id=str(effective_conversation_id),
    )

    config: dict[str, object] = {"configurable": {"thread_id": thread_id}}
    if "trace_context" in request_context:
        tc = request_context["trace_context"]
        config["metadata"] = config.get("metadata", {})
        config["metadata"]["langsmith-trace"] = tc.trace_id
    return admin_inputs, config


async def _finalise_admin_turn(
    *,
    question: str,
    user_id: int,
    conversation_id: int | None,
    is_compatibility_facade: bool,
    response_text: str,
    streamed_chars: int,
) -> AsyncGenerator[str, None]:
    """يحفظ الدور ويبثّ الإطار النهائي — ذراعا النجاح والفشل كلتاهما تُنهيان (§6.5)."""
    try:
        async with async_session_factory() as db_session:
            conv_id, _ = await _ensure_conversation(
                session=db_session,
                chat_scope="admin",
                user_id=user_id,
                question=question,
                requested_conversation_id=conversation_id,
                skip_user_message=is_compatibility_facade,
            )
            await _persist_assistant_message(
                session=db_session,
                chat_scope="admin",
                conversation_id=conv_id,
                content=response_text,
            )
        yield await _serialize_stream_frame(
            {"type": "assistant_delta", "payload": {"content": "\n\n✅ [DB SAVED]"}}
        )
        # D-047: لا تُكرِّر response_text إذا تم بث القطع بالفعل token-by-token،
        # لأن المتصفح يجمعها عبر mergeAssistantContent.
        # Signal Monolith that Orchestrator already persisted both messages
        yield await _serialize_stream_frame(
            {
                "type": "assistant_final",
                "payload": {"content": "" if streamed_chars > 0 else response_text},
                "persisted": True,
            }
        )
    except Exception as e:
        error_msg = str(e)
        yield await _serialize_stream_frame(
            {
                "type": "assistant_error",
                "payload": {"content": f"\n\n🚨 **SYSTEM DB ERROR:** {error_msg}"},
            }
        )
        # DB write failed — Monolith must handle persistence
        yield await _serialize_stream_frame(
            {
                "type": "assistant_final",
                "payload": {"content": response_text},
                "persisted": False,
            }
        )


@dataclass
class _AdminRunState:
    """ما يتراكم عبر بثّ الرسم: الردّ النهائي وعدد المحارف المبثوثة (D-047)."""

    final_resp: object = None
    streamed_chars: int = 0


async def _translate_graph_events(
    *,
    admin_app: object,
    admin_inputs: dict[str, object],
    config: dict[str, object],
    state: _AdminRunState,
) -> AsyncGenerator[str, None]:
    """يترجم أحداث LangGraph إلى إطارات العميل، ويُراكم الحالة في `state`."""
    async for event in admin_app.astream_events(admin_inputs, config=config, version="v2"):
        evt_type = event["event"]
        node_name = event.get("name", "")
        if evt_type in _PHASE_BY_EVENT and _is_reportable_node(node_name):
            yield await _serialize_stream_frame(
                {
                    "type": _PHASE_BY_EVENT[evt_type],
                    "payload": {"phase": node_name, "agent": "admin"},
                }
            )
        delta = _stream_delta_content(event, evt_type)
        if delta:
            state.streamed_chars += len(delta)
            yield await _serialize_stream_frame(
                {"type": "assistant_delta", "payload": {"content": delta}}
            )
        if evt_type == "on_chain_end":
            state.final_resp = _final_response_from_chain_end(event, state.final_resp)


def _admin_payload_from(request_context: dict[str, object]) -> dict[str, object]:
    """يَسِم السياق بالدور الإداري — مع بديلٍ دفاعي إن لم يكن قاموساً."""
    if isinstance(request_context, dict):
        request_context["is_admin"] = True
        request_context["role"] = "admin"
        return request_context
    return {"is_admin": True, "role": "admin"}


async def stream_admin_agent_chat(
    *,
    app_state: object,
    question: str,
    user_id: int,
    conversation_id: int | None,
    history_messages: list[dict[str, str]],
    request_context: dict[str, object],
    is_compatibility_facade: bool,
) -> AsyncGenerator[str, None]:
    """يبثّ دور الإدارة عبر رسم LangGraph الإداري ويحفظ الدور عند نجاحه."""
    try:
        admin_app = getattr(app_state, "admin_app", None)
        if admin_app is None:
            raise RuntimeError("LangGraph admin_app is required but was not found on app.state")

        admin_inputs, config = await _prepare_admin_run(
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            history_messages=history_messages,
            admin_payload=_admin_payload_from(request_context),
            request_context=request_context,
        )

        state = _AdminRunState()
        async for frame in _translate_graph_events(
            admin_app=admin_app, admin_inputs=admin_inputs, config=config, state=state
        ):
            yield frame

        # ISS-056: extract human-readable text only — never leak JSON envelope
        async for frame in _finalise_admin_turn(
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            is_compatibility_facade=is_compatibility_facade,
            response_text=_extract_human_readable_response(state.final_resp),
            streamed_chars=state.streamed_chars,
        ):
            yield frame
    except Exception:
        request_id = str(uuid.uuid4())
        logger.error(
            "Admin Chat Error",
            exc_info=True,
            extra={"request_id": request_id},
        )
        yield await _serialize_stream_frame(
            {
                "type": "assistant_error",
                "payload": {"content": _safe_assistant_error(request_id)},
            }
        )
