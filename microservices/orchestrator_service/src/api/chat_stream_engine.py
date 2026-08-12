"""محركا بثّ الدردشة عبر LangGraph — WS streaming + HTTP NDJSON generator.

مستخرَجة حرفياً من ``routes.py`` (D-168 Slice A4 — «العقدة الأشد»): يعتمدان على كل
طبقات ``chat_support`` الشقيقة — لا يستوردان من ``routes`` أبداً (طبقات باتجاه واحد).
ملاحظة monkeypatch (قاعدة D-168): الترقيع يستهدف الوحدة التي يعيش فيها المستدعي —
`_persist_assistant_message` المُستدعاة **داخل** المحرك تُرقَّع هنا لا في routes.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress

from fastapi import WebSocket

from microservices.orchestrator_service.src.core.database import (
    _psycopg_session_factory_proxy,
    async_session_factory,
    get_checkpointer,
)
from microservices.orchestrator_service.src.core.prom_metrics import (
    record_streaming_chunk,
    record_streaming_session,
)

from .chat_context import (
    _augment_ambiguous_objective,
    _build_graph_messages_graph,
    _context_gap_reason_for_followup,
    _detect_checkpoint_state,
    _extract_checkpoint_history,
)
from .chat_types import (
    MAX_CHECKPOINT_ANCHOR_MESSAGES,
    ChatRunContext,
    _extract_injected_exercise,
    _extract_support_level,
)
from .conversation_store import _persist_assistant_message
from .identity_access import (
    _merge_admin_inputs,
    _resolve_thread_id,
    _safe_assistant_error,
    _safe_conversation_id,
)
from .stream_serialization import (
    _append_telemetry_line,
    _extract_human_readable_response,
    _serialize_stream_frame,
)

logger = logging.getLogger(__name__)

active_background_tasks = set()


async def _stream_chat_langgraph(
    websocket: WebSocket,
    objective: str,
    context: ChatRunContext,
    chat_scope: str,
    conversation_id: int,
    app_graph: object = None,
    admin_payload: dict[str, object] | None = None,
    history_messages: list[dict[str, str]] | None = None,
) -> None:
    """يشغّل LangGraph الموحد لمسارات البحث والإدارة ويبث الأحداث."""
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=256)
    thread_id = _resolve_thread_id(context, conversation_id)
    safe_history = list(history_messages) if history_messages else []
    if not safe_history:
        safe_history = await _extract_checkpoint_history(
            thread_id=thread_id,
            max_messages=MAX_CHECKPOINT_ANCHOR_MESSAGES * 2,
        )
    context_gap_reason = _context_gap_reason_for_followup(objective, safe_history)
    if context_gap_reason is not None:
        history_size = len(safe_history)
        logger.warning(
            "[CONTEXT_GUARD] blocked ambiguous follow-up without anchor. conv_id=%s thread_id=%s reason=%s history_size=%s objective=%s",
            conversation_id,
            thread_id,
            context_gap_reason,
            history_size,
            objective[:120],
        )
        await websocket.send_json(
            {
                "type": "context_missing",
                "payload": {
                    "code": context_gap_reason,
                    "message": "تعذّر تحديد الكيان المرجعي من السياق الحالي.",
                    "conversation_id": conversation_id,
                    "thread_id": thread_id,
                    "history_size": history_size,
                    "source": "orchestrator.context_guard",
                },
            }
        )
        await websocket.send_json(
            {
                "type": "assistant_error",
                "payload": {
                    "content": "يرجى ذكر الكيان المقصود صراحةً (مثال: ما عاصمة الجزائر؟).",
                    "code": context_gap_reason,
                    "source": "orchestrator.context_guard",
                },
            }
        )
        return
    prepared_objective = _augment_ambiguous_objective(objective, safe_history)

    async def _runner():
        async def _safe_put(evt: dict[str, object]) -> None:
            try:
                queue.put_nowait(evt)
            except asyncio.QueueFull:
                logger.warning("[QUEUE_OVERFLOW] dropping event type=%s", evt.get("type"))

        try:
            _graph = app_graph or getattr(websocket.app.state, "app_graph", None)
            if _graph is None:
                raise RuntimeError("LangGraph instance is required but was not found on app.state")
            incoming_messages = safe_history
            await _append_telemetry_line(
                f"[TELEMETRY] INGRESS | "
                f"conversation_id={conversation_id!r} | "
                f"thread_id={thread_id!r} | "
                f"messages_in_request={len(incoming_messages)}"
            )
            config = {"configurable": {"thread_id": thread_id}}
            if "trace_context" in context:
                tc = context["trace_context"]
                config["metadata"] = config.get("metadata", {})
                config["metadata"]["langsmith-trace"] = tc.trace_id

            # فحص حالة الـ checkpointer لتحديد ما إذا كانت الحالة محفوظة مسبقاً
            checkpointer = get_checkpointer()
            _checkpointer_available, _checkpoint_has_state = False, False
            if checkpointer is None:
                await _append_telemetry_line("[TELEMETRY] CHECKPOINTER NOT IN SCOPE")
            else:
                _t = time.monotonic()
                try:
                    _ckpt = await checkpointer.aget(config)
                    _elapsed = time.monotonic() - _t
                    _checkpoint_has_state = _ckpt is not None
                    _checkpointer_available = True
                    _keys = list(_ckpt.channel_values.keys()) if _ckpt else None
                    await _append_telemetry_line(
                        f"[TELEMETRY] CHECKPOINTER | "
                        f"elapsed={_elapsed:.4f}s | "
                        f"state={'NONE — no prior state' if _ckpt is None else _keys}"
                    )
                except Exception as _e:
                    await _append_telemetry_line(
                        f"[TELEMETRY] CHECKPOINTER CRASHED | {type(_e).__name__}: {_e}"
                    )

            # بناء رسائل الإدخال بشكل صحيح:
            # - إذا كان checkpointer يحمل حالة → نمرر رسالة المستخدم الحالية فقط (delta)
            # - إذا لم تكن هناك حالة محفوظة → نمرر كامل التاريخ + الرسالة الحالية
            graph_messages = _build_graph_messages_graph(
                objective=prepared_objective,
                history_messages=safe_history if safe_history else None,
                checkpointer_available=_checkpointer_available,
                checkpoint_has_state=_checkpoint_has_state,
            )
            inputs: dict[str, object] = {"messages": graph_messages, "query": prepared_objective}
            inputs = _merge_admin_inputs(inputs, admin_payload if chat_scope == "admin" else None)
            # D-103: تمرير محتوى التمرين المحقون إلى حالة الرسم (مسار WS)
            _injected_exercise = _extract_injected_exercise(context)
            if _injected_exercise:
                inputs["exercise_content"] = _injected_exercise
            # D-115: تمرير support_level إلى حالة الرسم (مسار WS) — عمق التلميح السقراطي
            inputs["support_level"] = _extract_support_level(context)
            state_dict = inputs
            payload_messages = state_dict.get("messages", [])
            await _append_telemetry_line(
                f"[TELEMETRY] PRE-INVOKE | "
                f"checkpointer_available={_checkpointer_available} | "
                f"checkpoint_has_state={_checkpoint_has_state} | "
                f"messages type={type(payload_messages).__name__} | "
                f"count={len(payload_messages)} | "
                f"last_msg={str(payload_messages[-1])[:120] if payload_messages else 'EMPTY'}"
            )

            # ISS-STREAM-002 (جراحي — WS path): astream_events لا يُطلق on_custom_event
            # في LangGraph 1.2.0. الحل: astream(stream_mode=["custom","updates"])
            final_res = None
            ws_streamed_chars = 0

            async for _stream_mode, _chunk in _graph.astream(
                inputs,
                config=config,
                stream_mode=["custom", "updates"],
            ):
                if _stream_mode == "custom":
                    # token-by-token من stream_writer() في nodes
                    if isinstance(_chunk, dict) and _chunk.get("chunk_type") == "assistant_delta":
                        _content = _chunk.get("content")
                        if isinstance(_content, str) and _content:
                            ws_streamed_chars += len(_content)
                            await _safe_put(
                                {
                                    "type": "assistant_delta",
                                    "payload": {"content": _content},
                                }
                            )

                elif _stream_mode == "updates" and isinstance(_chunk, dict):
                    # state updates — phase_start + final_response
                    for _node_name, _node_output in _chunk.items():
                        if _node_name.startswith("__"):
                            continue
                        await _safe_put(
                            {
                                "type": "phase_start",
                                "payload": {"phase": _node_name, "agent": "orchestrator"},
                            }
                        )
                        if isinstance(_node_output, dict):
                            if "final_response" in _node_output:
                                final_res = {"final_response": _node_output["final_response"]}
                            elif _node_output.get("messages"):
                                _last = _node_output["messages"][-1]
                                if hasattr(_last, "content") and _last.content:
                                    final_res = {"final_response": _last.content}

            if checkpointer is not None:
                _t2 = time.monotonic()
                try:
                    _ckpt_after = await checkpointer.aget(config)
                    _elapsed2 = time.monotonic() - _t2
                    _msgs_saved = (
                        len(_ckpt_after.channel_values.get("messages", [])) if _ckpt_after else 0
                    )
                    await _append_telemetry_line(
                        f"[TELEMETRY] POST-INVOKE | "
                        f"elapsed={_elapsed2:.4f}s | "
                        f"messages_persisted={_msgs_saved} | "
                        f"state={'NONE — not saved' if _ckpt_after is None else 'SAVED'}"
                    )
                except Exception as _e:
                    await _append_telemetry_line(
                        f"[TELEMETRY] POST-INVOKE CRASHED | {type(_e).__name__}: {_e}"
                    )

            if not final_res:
                final_res = {"final_response": "لم يتم العثور على رد من النظام"}

            # D-047: attach streamed chars so consumer can suppress duplicated payload
            if isinstance(final_res, dict):
                final_res = dict(final_res)
                final_res["__streamed_chars"] = ws_streamed_chars

            await _safe_put({"type": "__DONE__", "result": final_res})
        except Exception as e:
            import traceback

            await _safe_put(
                {"type": "__ERROR__", "error": str(e), "traceback": traceback.format_exc()}
            )

    task = asyncio.create_task(_runner())
    active_background_tasks.add(task)

    def _cleanup_task(t: asyncio.Task) -> None:
        active_background_tasks.discard(t)
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.error("LangGraph task failed", exc_info=True)

    task.add_done_callback(_cleanup_task)
    _task_ref = task  # store reference to avoid GC

    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    await websocket.send_json(
        {
            "type": "RUN_STARTED",
            "payload": {
                "run_id": "sync-run",
                "seq": 1,
                "timestamp": now,
                "iteration": 0,
                "mode": context.get("mission_type", "auto"),
            },
        }
    )

    final_content = ""
    try:
        while True:
            evt = await queue.get()
            if evt["type"] == "__DONE__":
                run_data = evt["result"]

                # Extract the final response from our custom Unified Graph output
                final_resp = run_data.get("final_response")

                # ISS-056: never serialize dict envelope as JSON to the user.
                # SynthesizerNode returns {"المصدر","التمرين",...} — we want التمرين only.
                response_text = _extract_human_readable_response(final_resp)

                final_content = response_text
                logger.info(f"FINAL RESPONSE → {response_text[:100]}")

                # D-047: إذا بُثَّت قطع token-by-token خلال الـ stream،
                # لا نُكرِّر response_text في assistant_final لتجنّب duplicate text.
                _ws_streamed = (
                    run_data.get("__streamed_chars", 0) if isinstance(run_data, dict) else 0
                )
                _final_content = "" if _ws_streamed and _ws_streamed > 0 else response_text
                await websocket.send_json(
                    {
                        "type": "assistant_final",
                        "payload": {
                            "content": _final_content,
                            "status": "ok",
                            "run_id": "sync-run",
                            "timeline": [],
                            "graph_mode": "unified_stategraph",
                            "route_id": f"chat_ws_{chat_scope}",
                            "streamed_chars": int(_ws_streamed),
                        },
                    }
                )
                break
            if evt["type"] == "__ERROR__":
                request_id = str(uuid.uuid4())
                # The exception was raised in the background _runner task, so there
                # is no active exception here — log the captured error/traceback the
                # runner placed on the queue (exc_info=True would log "NoneType: None").
                logger.error(
                    "LangGraph streaming failure | request_id=%s chat_scope=%s | error=%s\n%s",
                    request_id,
                    chat_scope,
                    evt.get("error"),
                    evt.get("traceback"),
                )
                final_content = _safe_assistant_error(request_id)
                await websocket.send_json(
                    {"type": "assistant_error", "payload": {"content": final_content}}
                )
                break
            if evt["type"] == "phase_start":
                phase_name = (
                    evt["payload"].get("phase", "") if isinstance(evt["payload"], dict) else ""
                )
                agent_name = (
                    evt["payload"].get("agent", "") if isinstance(evt["payload"], dict) else ""
                )
                await websocket.send_json(
                    {
                        "type": "PHASE_STARTED",
                        "payload": {
                            "run_id": "sync-run",
                            "seq": 2,
                            "phase": phase_name,
                            "agent": agent_name,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    }
                )
                await websocket.send_json(
                    {
                        "type": "assistant_delta",
                        "payload": {"content": f"🔄 جاري التنفيذ: {phase_name}\n"},
                    }
                )
            elif evt["type"] == "phase_completed":
                phase_name = (
                    evt["payload"].get("phase", "") if isinstance(evt["payload"], dict) else ""
                )
                agent_name = (
                    evt["payload"].get("agent", "") if isinstance(evt["payload"], dict) else ""
                )
                await websocket.send_json(
                    {
                        "type": "PHASE_COMPLETED",
                        "payload": {
                            "run_id": "sync-run",
                            "seq": 3,
                            "phase": phase_name,
                            "agent": agent_name,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    }
                )
            elif evt["type"] == "loop_start":
                iteration = (
                    evt["payload"].get("iteration", 0) if isinstance(evt["payload"], dict) else 0
                )
                mode = (
                    evt["payload"].get("graph_mode", "standard")
                    if isinstance(evt["payload"], dict)
                    else "standard"
                )
                await websocket.send_json(
                    {
                        "type": "RUN_STARTED",
                        "payload": {
                            "run_id": f"sync-run:{iteration}",
                            "seq": 4,
                            "timestamp": datetime.now(UTC).isoformat(),
                            "iteration": iteration,
                            "mode": mode,
                        },
                    }
                )
            else:
                await websocket.send_json(evt)

        if final_content.strip():
            try:
                async with _psycopg_session_factory_proxy(
                    default_factory=async_session_factory
                ) as db_session:
                    await _persist_assistant_message(
                        session=db_session,
                        chat_scope=chat_scope,
                        conversation_id=conversation_id,
                        content=final_content,
                        mission_id=None,
                    )
                await websocket.send_json(
                    {"type": "assistant_delta", "payload": {"content": "\n\n✅ [DB SAVED]"}}
                )
            except Exception as e:
                error_msg = str(e)
                await websocket.send_json(
                    {
                        "type": "assistant_delta",
                        "payload": {"content": f"\n\n🚨 **SYSTEM DB ERROR:** {error_msg}"},
                    }
                )
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    await websocket.send_json({"type": "complete", "payload": {}})


async def _run_chat_langgraph(
    objective: str,
    context: ChatRunContext,
    app_graph: object = None,
    admin_payload: dict[str, object] | None = None,
    history_messages: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """يشغّل LangGraph كعمود فقري لرحلة chat ويعيد حمولة موحدة قابلة للبث (HTTP legacy fallback)."""
    if not app_graph:
        raise RuntimeError("LangGraph instance is required but was not found on app.state")
    requested_conversation_id = context.get("conversation_id") if context else None
    safe_conversation_id = _safe_conversation_id(requested_conversation_id)
    conversation_id: int | str = (
        safe_conversation_id if safe_conversation_id is not None else str(uuid.uuid4())
    )
    thread_id = _resolve_thread_id(context, conversation_id)
    prepared_objective = _augment_ambiguous_objective(objective, history_messages)
    config = {"configurable": {"thread_id": thread_id}}
    if "trace_context" in context:
        tc = context["trace_context"]
        config["metadata"] = config.get("metadata", {})
        config["metadata"]["langsmith-trace"] = tc.trace_id

    logger.info(
        "[THREAD_BINDING] channel=http thread_id=%s source=%s conversation_id=%s",
        thread_id,
        "request_context"
        if "thread_id" in context or "session_id" in context
        else "conversation_fallback",
        str(conversation_id),
    )
    # فحص حالة الـ checkpointer لتحديد ما إذا كانت الحالة محفوظة مسبقاً
    _checkpointer_available, _checkpoint_has_state = await _detect_checkpoint_state(thread_id)
    graph_messages = _build_graph_messages_graph(
        objective=prepared_objective,
        history_messages=history_messages,
        checkpointer_available=_checkpointer_available,
        checkpoint_has_state=_checkpoint_has_state,
    )
    inputs: dict[str, object] = {"messages": graph_messages, "query": prepared_objective}
    inputs = _merge_admin_inputs(inputs, admin_payload)
    # D-103: تمرير محتوى التمرين المحقون إلى حالة الرسم (مسار HTTP — يستدعيه الـ monolith)
    _injected_exercise = _extract_injected_exercise(context)
    if _injected_exercise:
        logger.info(
            "[D-103] injected_exercise chars=%s ref=%s",
            len(_injected_exercise),
            str(context.get("exercise_ref", ""))[:120],
        )
        inputs["exercise_content"] = _injected_exercise

    # D-115: تمرير support_level إلى حالة الرسم (مسار HTTP) — عمق التلميح السقراطي
    inputs["support_level"] = _extract_support_level(context)

    # ISS-STREAM-002 (جراحي): astream_events لا يُطلق on_custom_event في LangGraph 1.2.0
    # عند استخدام stream_writer(). الحل: astream(stream_mode=["custom","updates"]) يُعيد
    # custom chunks مباشرة + state updates لاستخراج final_response.
    # المرجع: اختبار مباشر أثبت أن writer() يُستدعى لكن on_custom_event لا يُطلق أبداً.
    import time as _time_mod

    streamed_chars = 0
    final_resp = None
    _stream_start = _time_mod.perf_counter()
    _active_node = "unknown"

    # المرحلة 1: بث الـ phase_start events أولاً (لا تحتاج astream_events)
    # نُرسل phase_start لكل node عبر updates stream
    async for stream_mode, chunk in app_graph.astream(
        inputs,
        config=config,
        stream_mode=["custom", "updates"],
    ):
        if (
            stream_mode == "custom"
            and isinstance(chunk, dict)
            and chunk.get("chunk_type") == "assistant_delta"
        ):
            # custom chunks من stream_writer() — هذا هو مسار token-by-token
            content = chunk.get("content")
            node_name = chunk.get("node", _active_node)
            if isinstance(content, str) and content:
                streamed_chars += len(content)
                # ISS-STREAM-002: تسجيل كل chunk في Prometheus
                import contextlib

                with contextlib.suppress(Exception):
                    record_streaming_chunk("http", str(node_name), len(content))
                yield await _serialize_stream_frame(
                    {"type": "assistant_delta", "payload": {"content": content}}
                )

        elif stream_mode == "updates" and isinstance(chunk, dict):
            # state updates — نستخرج منها phase_start وfinal_response
            for node_name, node_output in chunk.items():
                if node_name.startswith("__"):
                    continue
                _active_node = node_name
                # phase_start لكل node
                yield await _serialize_stream_frame(
                    {
                        "type": "phase_start",
                        "payload": {"phase": node_name, "agent": "orchestrator"},
                    }
                )
                # استخراج final_response من آخر node ينتجه
                if isinstance(node_output, dict):
                    if "final_response" in node_output:
                        final_resp = node_output["final_response"]
                    elif node_output.get("messages"):
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, "content") and last_msg.content:
                            final_resp = last_msg.content

    # ISS-056: never leak SynthesizerNode dict envelope as JSON to the user
    response_text = _extract_human_readable_response(final_resp)

    # ISS-STREAM-002: تسجيل الجلسة الكاملة في Prometheus
    import contextlib

    with contextlib.suppress(Exception):
        _stream_duration = _time_mod.perf_counter() - _stream_start
        _session_status = "success" if streamed_chars > 0 else "fallback"
        record_streaming_session("http", _session_status, _stream_duration)

    # إذا بُثَّت قطع كافية → assistant_final بـ content="" (الـ deltas كافية)
    # إذا لم تُبَث أي قطعة (مثلاً النموذج لا يدعم streaming) → نُرسل النص كاملاً
    if streamed_chars == 0:
        yield await _serialize_stream_frame(
            {
                "type": "assistant_final",
                "payload": {
                    "content": response_text,
                    "status": "ok",
                    "run_id": "http-run",
                    "graph_mode": "unified_stategraph",
                },
            }
        )
    else:
        yield await _serialize_stream_frame(
            {
                "type": "assistant_final",
                "payload": {
                    "content": "",
                    "status": "ok",
                    "run_id": "http-run",
                    "graph_mode": "unified_stategraph",
                    "streamed_chars": streamed_chars,
                },
            }
        )
