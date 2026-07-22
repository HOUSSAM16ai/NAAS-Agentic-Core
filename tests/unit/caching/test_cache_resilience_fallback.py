"""Cognitive-cache resilience fallback (D-180 / ISS-133).

When the full model chain is exhausted (typically a transient global 429),
``OpenRouterClient.stream_chat`` replays a high-resonance prior answer for the
SAME question in the SAME context *before* dropping to the safety net — this is
what makes the platform "answer every question". These tests pin the contract:

* recall fires ONLY after the model chain is exhausted (never on success);
* a hit replays the cached chunks, not the safety-net stub;
* the ``COGNITIVE_CACHE_RESILIENCE_ENABLED=0`` kill-switch disables it;
* recall never short-circuits a live model on the happy path.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from app.core.cognitive_cache import CognitiveResonanceEngine
from app.core.gateway import simple_client as sc
from app.core.gateway.exceptions import AIRateLimitError
from app.core.gateway.simple_client import OpenRouterClient, _ModelOutcome
from app.core.types import JSONDict

_PROMPT = "كيف أحسب مشتقة الدالة sin(x)"
_CACHED_CHUNK: JSONDict = {"choices": [{"delta": {"content": "المشتقة هي cos(x)"}}]}
_SAFETY_CHUNK: JSONDict = {"choices": [{"delta": {"content": "SAFETY_NET"}}]}


class _FakeSafetyNet:
    async def stream_safety_response(self) -> AsyncGenerator[JSONDict, None]:
        yield _SAFETY_CHUNK


def _build_client(engine: CognitiveResonanceEngine) -> OpenRouterClient:
    return OpenRouterClient(
        api_key="dummy",
        primary_model="model-a",
        fallback_models=["model-b"],
        cognitive_engine=engine,
        safety_net=_FakeSafetyNet(),  # type: ignore[arg-type]
    )


@pytest.fixture(autouse=True)
def _no_network_no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    # stream_chat calls ConnectionManager.get_client() and may sleep on backoff.
    monkeypatch.setattr(sc.ConnectionManager, "get_client", staticmethod(lambda: None))

    async def _instant_sleep(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(sc.asyncio, "sleep", _instant_sleep)


def _patch_all_rate_limited(monkeypatch: pytest.MonkeyPatch, client: OpenRouterClient) -> None:
    """Force every model attempt to fail with a 429 → chain exhausts."""

    async def _fail(*_a: object, **_k: object) -> AsyncGenerator[object, None]:
        yield _ModelOutcome(
            emitted_content=False, error=AIRateLimitError("429", retry_after=0.0), chunks=[]
        )

    monkeypatch.setattr(client, "_attempt_model", _fail)


async def _collect(client: OpenRouterClient, prompt: str) -> list[JSONDict]:
    messages: list[JSONDict] = [{"role": "user", "content": prompt}]
    return [chunk async for chunk in client.stream_chat(messages)]


def _memorize_for(client: OpenRouterClient, engine: CognitiveResonanceEngine, prompt: str) -> None:
    messages: list[JSONDict] = [{"role": "user", "content": prompt}]
    ctx = client._get_context_hash(messages)
    engine.memorize(prompt, ctx, [_CACHED_CHUNK])


@pytest.mark.asyncio
async def test_recall_replays_on_chain_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNITIVE_CACHE_RESILIENCE_ENABLED", "1")
    engine = CognitiveResonanceEngine()
    client = _build_client(engine)
    _memorize_for(client, engine, _PROMPT)
    _patch_all_rate_limited(monkeypatch, client)

    chunks = await _collect(client, _PROMPT)

    assert _CACHED_CHUNK in chunks, "resilience recall must replay the cached answer"
    assert _SAFETY_CHUNK not in chunks, "safety net must be skipped when recall hits"


@pytest.mark.asyncio
async def test_safety_net_when_no_cache_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNITIVE_CACHE_RESILIENCE_ENABLED", "1")
    engine = CognitiveResonanceEngine()  # empty — no engram to recall
    client = _build_client(engine)
    _patch_all_rate_limited(monkeypatch, client)

    chunks = await _collect(client, _PROMPT)

    assert _SAFETY_CHUNK in chunks
    assert _CACHED_CHUNK not in chunks


@pytest.mark.asyncio
async def test_flag_off_disables_recall(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNITIVE_CACHE_RESILIENCE_ENABLED", "0")
    engine = CognitiveResonanceEngine()
    client = _build_client(engine)
    _memorize_for(client, engine, _PROMPT)  # cache HAS the answer...
    _patch_all_rate_limited(monkeypatch, client)

    chunks = await _collect(client, _PROMPT)

    # ...but the kill-switch forces the safety net instead of the cached replay.
    assert _SAFETY_CHUNK in chunks
    assert _CACHED_CHUNK not in chunks


@pytest.mark.asyncio
async def test_recall_not_used_on_successful_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNITIVE_CACHE_RESILIENCE_ENABLED", "1")
    engine = CognitiveResonanceEngine()
    client = _build_client(engine)
    live_chunk: JSONDict = {"choices": [{"delta": {"content": "LIVE_MODEL_ANSWER"}}]}

    async def _succeed(*_a: object, **_k: object) -> AsyncGenerator[object, None]:
        yield live_chunk
        yield _ModelOutcome(emitted_content=True, error=None, chunks=[live_chunk])

    monkeypatch.setattr(client, "_attempt_model", _succeed)

    chunks = await _collect(client, _PROMPT)

    assert live_chunk in chunks
    assert _SAFETY_CHUNK not in chunks
    # The live turn is memorized so a *future* outage can recall it.
    ctx = client._get_context_hash([{"role": "user", "content": _PROMPT}])
    assert engine.recall(_PROMPT, ctx) == [live_chunk]
