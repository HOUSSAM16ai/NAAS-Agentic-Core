"""Regression tests for the orchestrator graph deadlock fix.

Root cause (resolved here): the unified StateGraph hung indefinitely at its
entry node because the structured-output intent classification was unbounded
I/O — ``dspy.LM`` had no ``timeout`` and ``SupervisorNode`` awaited it with no
guard. A stalled OpenRouter connection blocked the worker thread forever and
the deterministic free-response fallback was never reached.

These tests lock in the deterministic-routing guarantees and the bounded /
graceful-fallback behaviour. They import only from the import-light ``main``
module (no DB / settings side effects).
"""

import asyncio

import pytest

from microservices.orchestrator_service.src.services.overmind.graph.main import (
    SupervisorNode,
    route_intent,
)

_VALID_BRANCHES = {"educational", "admin", "tool", "chat", "general_knowledge"}


@pytest.mark.parametrize("unknown", ["GIBBERISH_XYZ", "", "search", None])
def test_route_intent_always_returns_a_valid_branch(unknown):
    """route_intent must never return a value absent from the conditional-edge
    map — otherwise LangGraph raises an 'unknown branch' error (a hard exit
    condition gap)."""
    state = {} if unknown is None else {"intent": unknown}
    assert route_intent(state) in _VALID_BRANCHES


@pytest.mark.parametrize("intent", sorted(_VALID_BRANCHES))
def test_route_intent_passes_through_valid_intents(intent):
    assert route_intent({"intent": intent}) == intent


@pytest.mark.asyncio
async def test_supervisor_falls_back_when_classifier_raises():
    """If structured-output classification fails, SupervisorNode must still
    return a valid deterministic route instead of hanging or crashing."""
    node = SupervisorNode()

    def _failing_classifier(**_kwargs):
        raise RuntimeError("structured output enforcement failed")

    node.dspy_classifier = _failing_classifier
    result = await node({"query": "اشرح نظرية النسبية بالتفصيل", "messages": []})
    assert result.get("intent") in _VALID_BRANCHES


@pytest.mark.asyncio
async def test_supervisor_classification_is_timeout_bounded():
    """A stalled classifier must not hang the entry node: the wait_for guard
    fires and routing falls through to the deterministic heuristic. Bound the
    test well under the production 30s guard via a patched, near-instant guard
    so CI stays fast while still exercising the real code path."""
    node = SupervisorNode()

    def _stalling_classifier(**_kwargs):
        # Cooperative stall longer than the (patched) guard window.
        import time

        time.sleep(2.0)
        raise RuntimeError("should never be reached before timeout")

    node.dspy_classifier = _stalling_classifier

    real_wait_for = asyncio.wait_for

    async def _fast_wait_for(awaitable, timeout):
        return await real_wait_for(awaitable, timeout=0.2)

    # D-173 Stage 2c (D-168 late-binding): the timeout guard's caller moved from
    # graph.main into the extracted graph.nodes module. Patch where the call
    # site lives — graph.main only re-exports SupervisorNode (noqa F401).
    import microservices.orchestrator_service.src.services.overmind.graph.nodes as graph_nodes

    original = graph_nodes.asyncio.wait_for
    graph_nodes.asyncio.wait_for = _fast_wait_for
    try:
        started = asyncio.get_event_loop().time()
        result = await node({"query": "اشرح نظرية النسبية بالتفصيل", "messages": []})
        elapsed = asyncio.get_event_loop().time() - started
    finally:
        graph_nodes.asyncio.wait_for = original

    assert result.get("intent") in _VALID_BRANCHES
    assert elapsed < 1.5, f"entry node was not timeout-bounded: {elapsed:.2f}s"
