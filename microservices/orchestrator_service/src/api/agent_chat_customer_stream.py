"""مولّد البثّ للزبون في `/agent/chat` — D-168 Slice A7.

نقلٌ **حرفيّ** لمُغلَقة `_stream_generator` من `routes.py:1135-1237`. الأسماء المُغلَقة
(`agent` · `request` · `context` · `is_compatibility_facade`) صارت وسائط صريحة، ولا
شيء غير ذلك تغيّر.

⚠️ هذا المسار يشغّل `OrchestratorAgent` **لا** LangGraph — وهو مقصود: `/agent/chat`
هو ذراع التراجع في D-021، وتحويله إلى LangGraph يحذف الرافعة نفسها التي وُجد لأجلها.

## سلوكان قائمان يُنقَلان كما هما (موثَّقان لا مُصلَحان في هذه الجولة)

- **الدور الفارغ صامت تماماً:** بلا محتوى وبلا `final_chunk` لا يُبَثّ أيّ إطار —
  والعميل يتلقّى 200 فارغاً، بينما §6.5 تطلب إطاراً نهائياً واحداً لكلّ دور.
- **نصّ الاستثناء الخام يبلغ الطالب:** ذراع فشل الحفظ تبثّ
  `SYSTEM DB ERROR: {error_msg}` بينما المِظلّة الخارجية تستعمل `_safe_assistant_error`
  الآمنة — تسريبٌ غير متّسق.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator

from microservices.orchestrator_service.src.core.database import async_session_factory

from .chat_context import _augment_ambiguous_objective, _build_graph_messages_manual
from .chat_types import ChatRunContext
from .conversation_store import _ensure_conversation, _persist_assistant_message
from .identity_access import _safe_assistant_error
from .stream_serialization import _serialize_stream_frame

logger = logging.getLogger(__name__)

#: «لا تبثّ هذه القطعة» — مُميَّز عن `None` لأن القطعة نفسها قد تكون `None` مشروعاً.
_NO_FRAME = object()


def _already_a_frame(chunk: str) -> dict[str, object] | None:
    """يكشف سلسلةً هي في الحقيقة إطارٌ مُسلسَل — دفاعٌ في العمق ضدّ ISS-156.

    الكشف **دقيق لا تخميني**: يشترط `json.loads` ناجحاً **و**قاموساً يحمل مفتاح
    `type`. فنثرُ الطالب أو المعلّم لا يمكن أن يُقرأ إطاراً بالخطأ، ومُنتِجٌ يعود
    غداً فيُسلسل قبل أن يُسلّم لا يستطيع إعادة العطب.
    """
    text = chunk.lstrip()
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) and "type" in parsed else None


def _classify_agent_chunk(chunk: object) -> tuple[str | None, object, bool]:
    """يصنّف قطعة الوكيل إلى (نصٌّ يُراكَم، إطارٌ يُبَثّ، أهي النهائية).

    الأشكال الأربعة التي يُنتجها `OrchestratorAgent.run` — والنهائية **تُلتقط ولا
    تُبَثّ** لأن الإطار النهائي يُبنى لاحقاً حاملاً راية `persisted` (§6.5).

    ⚠️ **المُراكَم نصُّ الطالب لا المظروف**: `full_ai_response` هو ما يُكتب في
    `customer_messages`، فتراكُم المظروف يُسمّم الصفّ المحفوظ إلى الأبد (ISS-156 —
    مُثبَتٌ حيّاً بـSQL على قاعدة حقيقية قبل الإصلاح).
    """
    if isinstance(chunk, str):
        framed = _already_a_frame(chunk)
        if framed is not None:
            return _classify_agent_chunk(framed)
        return chunk, chunk, False
    if isinstance(chunk, dict) and chunk.get("type") == "assistant_delta":
        content = chunk.get("payload", {}).get("content", "")
        return (str(content) if content else None), chunk, False
    if isinstance(chunk, dict) and chunk.get("type") == "assistant_final":
        content = chunk.get("payload", {}).get("content", "")
        return (str(content) if content else None), _NO_FRAME, True
    return None, chunk, False


def _prepare_customer_run(
    *,
    question: str,
    history_messages: list[dict[str, str]],
) -> tuple[str, list[object]]:
    """يبني الهدف المُثرى ورسائل السياق التي يستقبلها الوكيل."""
    prepared_objective = _augment_ambiguous_objective(question, history_messages)

    # Use _build_graph_messages to properly seed history for the agent context
    langchain_msgs = _build_graph_messages_manual(
        objective=prepared_objective,
        history_messages=history_messages,
    )
    return prepared_objective, langchain_msgs


async def _finalise_customer_turn(
    *,
    question: str,
    user_id: int,
    conversation_id: int | None,
    is_compatibility_facade: bool,
    full_ai_response: str,
) -> AsyncGenerator[str, None]:
    """يحفظ الدور ثمّ يبثّ الإطار النهائي حاملاً ما إذا كان الأوركستريتور قد حفظ."""
    orchestrator_persisted = False
    try:
        async with async_session_factory() as db_session:
            conv_id, _ = await _ensure_conversation(
                session=db_session,
                chat_scope="customer",
                user_id=user_id,
                question=question,
                requested_conversation_id=conversation_id,
                skip_user_message=is_compatibility_facade,
            )
            await _persist_assistant_message(
                session=db_session,
                chat_scope="customer",
                conversation_id=conv_id,
                content=full_ai_response,
            )
        orchestrator_persisted = True
        yield await _serialize_stream_frame(
            {"type": "assistant_delta", "payload": {"content": "\n\n✅ [DB SAVED]"}}
        )
    except Exception as e:
        error_msg = str(e)
        yield await _serialize_stream_frame(
            {
                "type": "assistant_error",
                "payload": {"content": f"\n\n🚨 **SYSTEM DB ERROR:** {error_msg}"},
            }
        )
    # Signal Monolith whether Orchestrator handled persistence
    yield await _serialize_stream_frame(
        {
            "type": "assistant_final",
            "payload": {"content": full_ai_response},
            "persisted": orchestrator_persisted,
        }
    )


async def stream_customer_agent_chat(
    *,
    agent: object,
    question: str,
    user_id: int,
    conversation_id: int | None,
    history_messages: list[dict[str, str]],
    context: ChatRunContext,
    is_compatibility_facade: bool,
) -> AsyncGenerator[str, None]:
    """يبثّ دور الزبون عبر `OrchestratorAgent` ويحفظ الدور عند وجود محتوى."""
    try:
        prepared_objective, langchain_msgs = _prepare_customer_run(
            question=question, history_messages=history_messages
        )
        run_result = agent.run(prepared_objective, context=context, history_messages=langchain_msgs)
        ai_chunks: list[str] = []
        final_chunk = None
        async for chunk in run_result:
            text, frame, is_final = _classify_agent_chunk(chunk)
            if text:
                ai_chunks.append(text)
            if frame is not _NO_FRAME:
                yield await _serialize_stream_frame(frame)
            if is_final:
                final_chunk = chunk

        # The run completed successfully, trigger persistence
        full_ai_response = "".join(ai_chunks)
        if full_ai_response:
            async for frame in _finalise_customer_turn(
                question=question,
                user_id=user_id,
                conversation_id=conversation_id,
                is_compatibility_facade=is_compatibility_facade,
                full_ai_response=full_ai_response,
            ):
                yield frame
        elif final_chunk:
            # No AI response to persist — forward original final_chunk without persistence flag
            yield await _serialize_stream_frame(final_chunk)

    except Exception:
        request_id = str(uuid.uuid4())
        logger.error(
            "Agent Chat Error",
            exc_info=True,
            extra={"request_id": request_id},
        )
        yield await _serialize_stream_frame(
            {
                "type": "assistant_error",
                "payload": {"content": _safe_assistant_error(request_id)},
            }
        )
