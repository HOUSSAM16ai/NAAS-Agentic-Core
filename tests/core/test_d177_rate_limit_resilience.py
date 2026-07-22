"""D-177 — "answer every question" under free-tier rate limits.

Covers the bounded second pass over 429 models, safety-net-only-after-exhaustion,
the first-token timeout classification, retry-after parsing, and the mandatory
cognitive-engine None guard.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.gateway.exceptions import AIRateLimitError
from app.core.gateway.simple_client import OpenRouterClient, _parse_retry_after


def _delta(text: str) -> dict:
    return {"choices": [{"delta": {"content": text}}]}


def _make_client(monkeypatch, behaviors: dict[str, list]) -> OpenRouterClient:
    """Build a client whose ``_stream_model`` replays scripted per-model behavior.

    ``behaviors[model_id]`` is a list (one entry per attempt): either the string
    "content" (stream one real chunk then finish), or an Exception to raise.
    """
    safety = MagicMock()

    async def _safety_stream() -> AsyncGenerator[dict, None]:
        yield _delta("SAFETY_NET")

    safety.stream_safety_response = _safety_stream

    client = OpenRouterClient(
        api_key="k",
        primary_model="primary",
        fallback_models=["fb1", "fb2"],
        cognitive_engine=None,  # exercises the None guard
        safety_net=safety,
    )

    calls: dict[str, int] = {}

    async def fake_stream_model(_client, model_id, _messages, max_tokens=None):
        idx = calls.get(model_id, 0)
        calls[model_id] = idx + 1
        script = behaviors.get(model_id, [])
        action = script[idx] if idx < len(script) else script[-1] if script else RuntimeError("x")
        if isinstance(action, Exception):
            raise action
        yield _delta(f"{model_id}-ok")

    monkeypatch.setattr(client, "_stream_model", fake_stream_model)
    return client


async def _collect(client) -> str:
    out = []
    async for chunk in client.stream_chat([{"role": "user", "content": "q"}]):
        ch = chunk.get("choices", [])
        if ch:
            out.append(ch[0].get("delta", {}).get("content") or "")
    return "".join(out)


@pytest.mark.asyncio
async def test_second_pass_recovers_transient_429(monkeypatch):
    """All models 429 on pass 1, but primary succeeds on pass 2 → real answer."""
    behaviors = {
        "primary": [AIRateLimitError("429", retry_after=0.01), "content"],
        "fb1": [AIRateLimitError("429", retry_after=0.01)],
        "fb2": [AIRateLimitError("429", retry_after=0.01)],
    }
    client = _make_client(monkeypatch, behaviors)
    result = await _collect(client)
    assert "primary-ok" in result
    assert "SAFETY_NET" not in result


@pytest.mark.asyncio
async def test_safety_net_only_after_both_passes(monkeypatch):
    """Persistent 429 on every model across both passes → safety net."""
    behaviors = {
        "primary": [AIRateLimitError("429", retry_after=0.01)],
        "fb1": [AIRateLimitError("429", retry_after=0.01)],
        "fb2": [AIRateLimitError("429", retry_after=0.01)],
    }
    client = _make_client(monkeypatch, behaviors)
    result = await _collect(client)
    assert result == "SAFETY_NET"


@pytest.mark.asyncio
async def test_first_working_model_wins_no_safety(monkeypatch):
    """Primary 429 but fb1 answers on pass 1 → no second pass, no safety net."""
    behaviors = {
        "primary": [AIRateLimitError("429", retry_after=0.01)],
        "fb1": ["content"],
        "fb2": ["content"],
    }
    client = _make_client(monkeypatch, behaviors)
    result = await _collect(client)
    assert result == "fb1-ok"


@pytest.mark.asyncio
async def test_hard_failures_not_retried_but_safety_serves(monkeypatch):
    """Non-429 failures are not retried; with nothing left, safety net serves."""
    behaviors = {
        "primary": [ValueError("empty_completion")],
        "fb1": [httpx.ConnectError("down")],
        "fb2": [TimeoutError("first_token_timeout")],
    }
    client = _make_client(monkeypatch, behaviors)
    result = await _collect(client)
    assert result == "SAFETY_NET"


def test_parse_retry_after_header():
    resp = httpx.Response(
        429, headers={"Retry-After": "7"}, request=httpx.Request("POST", "http://x")
    )
    assert _parse_retry_after(resp) == 7.0


def test_parse_retry_after_body():
    resp = httpx.Response(
        429,
        json={"error": {"metadata": {"retry_after_seconds": 30}}},
        request=httpx.Request("POST", "http://x"),
    )
    assert _parse_retry_after(resp) == 30.0


def test_parse_retry_after_absent():
    resp = httpx.Response(429, text="nope", request=httpx.Request("POST", "http://x"))
    assert _parse_retry_after(resp) is None
