import logging

from langchain_core.messages import AIMessage

from microservices.orchestrator_service.src.core.ai_gateway import get_ai_client

from .main import AgentState, format_conversation_history

logger = logging.getLogger("graph")


def _get_optional_stream_writer():
    """يحاول الحصول على stream_writer من LangGraph — يُعيد None إذا لم يكن مُتاحاً.

    D-048: متوفر فقط عندما يعمل الـ graph في وضع streaming (astream/astream_events).
    في وضع batch (ainvoke) يُعيد None والعقدة تعمل بالطريقة العادية.
    """
    try:
        from langgraph.config import get_stream_writer

        return get_stream_writer()
    except Exception:
        return None


class GeneralKnowledgeNode:
    """عقدة مسؤولة عن الإجابة على أسئلة المعرفة العامة (مثل العواصم، التعداد السكاني، إلخ)."""

    async def __call__(self, state: AgentState) -> dict:
        import time

        from .telemetry import emit_telemetry

        start_time = time.time()
        messages = state.get("messages", [])

        query = state.get("query")
        if not query and messages:
            query = messages[-1].content
        query = str(query or "").strip()

        # Memory is accurate and automatically loaded by Checkpointer.
        # We no longer amputate the prompt_messages via slicing.
        prompt_messages = messages
        history = format_conversation_history(prompt_messages)

        if not history.strip():
            logger.debug("GeneralKnowledgeNode: empty history for query=%.60s", query)

        ai_client = get_ai_client()

        system_content = "أجب بدقة اعتماداً على سياق المحادثة. لا تتجاهل السياق أبداً."
        user_content = f"السياق:\n{history}\n\nالسؤال:\n{query}"

        writer = _get_optional_stream_writer()
        try:
            if writer is not None:
                # D-048: STREAMING path — يبث token-by-token عبر custom events
                full_content_parts: list[str] = []
                stream_messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ]
                async for chunk in ai_client.stream_chat(stream_messages):
                    try:
                        choices = chunk.get("choices") if isinstance(chunk, dict) else None
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {}) or {}
                        content = delta.get("content")
                        if not isinstance(content, str) or not content:
                            continue
                        full_content_parts.append(content)
                        writer(
                            {
                                "chunk_type": "assistant_delta",
                                "content": content,
                                "node": "general_knowledge",
                            }
                        )
                    except Exception:
                        continue
                response_content = "".join(full_content_parts).strip()
                if not response_content:
                    raise ValueError("Empty stream from LLM")
            else:
                # Non-streaming path — للحفاظ على التوافق مع batch/test mode
                response_content = await ai_client.send_message(
                    system_prompt=system_content, user_message=user_content, temperature=0.3
                )

            emit_telemetry(node_name="GeneralKnowledgeNode", start_time=start_time, state=state)
            return {
                "final_response": response_content.strip(),
                "messages": [AIMessage(content=response_content.strip())],
            }

        except Exception as error:
            logger.error(f"GeneralKnowledgeNode failed: {error}", exc_info=True)
            fallback_response = "عذراً، لم أتمكن من استرجاع هذه المعلومة الآن."
            emit_telemetry(
                node_name="GeneralKnowledgeNode", start_time=start_time, state=state, error=error
            )
            return {
                "final_response": fallback_response,
                "messages": [AIMessage(content=fallback_response)],
            }
