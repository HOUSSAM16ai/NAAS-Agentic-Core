import logging

from langchain_core.messages import AIMessage

from microservices.orchestrator_service.src.services.llm.client import (
    get_ai_client as get_llm_client,
)
from microservices.orchestrator_service.src.services.overmind.latex_normalizer import (
    LatexStreamNormalizer,
    normalize_latex,
)

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

        system_content = "أجب بدقة اعتماداً على سياق المحادثة. لا تتجاهل السياق أبداً."
        user_content = f"السياق:\n{history}\n\nالسؤال:\n{query}"

        # ISS-STREAM-002: استخدام get_llm_client() مباشرة للحصول على extract_stream_content()
        llm_client = get_llm_client()
        writer = _get_optional_stream_writer()
        try:
            if writer is not None:
                # D-048: STREAMING path — يبث token-by-token عبر custom events
                # D-061 (ISS-074): LatexStreamNormalizer يطبِّع \[...\] → $$...$$
                # على الـ chunks قبل إرسالها للعميل — يحل كارثة LaTeX الخام.
                normalizer = LatexStreamNormalizer()
                full_content_parts: list[str] = []
                stream_messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ]
                async for chunk in llm_client.stream_chat(stream_messages):
                    try:
                        # ISS-STREAM-002: استخدام extract_stream_content بدل chunk.get()
                        # stream_chat يُعيد ChatCompletionChunk objects وليس dicts
                        content = llm_client.extract_stream_content(chunk)
                        if not content:
                            continue
                        for safe in normalizer.feed(content):
                            full_content_parts.append(safe)
                            writer(
                                {
                                    "chunk_type": "assistant_delta",
                                    "content": safe,
                                    "node": "general_knowledge",
                                }
                            )
                    except Exception:
                        continue
                # flush أي محتوى متبقٍ في الـ buffer
                for tail in normalizer.flush():
                    full_content_parts.append(tail)
                    writer(
                        {
                            "chunk_type": "assistant_delta",
                            "content": tail,
                            "node": "general_knowledge",
                        }
                    )
                response_content = "".join(full_content_parts).strip()
                if not response_content:
                    raise ValueError("Empty stream from LLM")
            else:
                # Non-streaming path — للحفاظ على التوافق مع batch/test mode
                resp = await llm_client.generate(
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.3,
                )
                raw = resp.choices[0].message.content or ""
                response_content = normalize_latex(raw)

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
