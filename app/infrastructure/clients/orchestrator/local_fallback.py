import asyncio
import logging

from httpx import Response
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _mark_fallback(path: str) -> None:
    """Best-effort telemetry hook. Must never break the fallback flow."""
    try:
        from app.telemetry.path_observer import mark_fallback_used  # lazy import: avoids import cycles / optional module

        mark_fallback_used(path)
    except Exception as e:
        logger.warning(f"Telemetry logging error (silenced): {e}")


class LocalFallbackMixin:
    """
    Mixin that intercepts failed HTTP calls to the orchestrator and falls back
    to an in-memory execution of the graph.
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def call_with_fallback(self, func, path: str, *args, **kwargs) -> Response:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Orchestrator HTTP call failed ({path}): {e}. Attempting local fallback.")

            # Record telemetry asynchronously to avoid blocking the critical path
            _mark_fallback(path)

            from app.services.chat.local_graph import _get_graph

            graph = _get_graph()

            if path == "chat_with_agent":
                envelope = args[0]
                thread_id = args[1]

                # Execute graph logic inline as fallback
                result = await graph.ainvoke(
                    {"messages": envelope.messages},
                    config={"configurable": {"thread_id": thread_id}},
                )

                # Create synthetic response to maintain contract
                return Response(
                    200, json={"content": result["messages"][-1].content}
                )

            logger.error(f"Fallback not implemented for path: {path}")
            raise e
