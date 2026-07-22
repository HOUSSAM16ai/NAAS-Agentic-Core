#!/usr/bin/env python3
"""Live E2E — Cognitive cache revolution (D-180 / ISS-133).

Proves, against the REAL OpenRouter gateway, that:

  1. A real Arabic question streams a real Arabic answer through the gateway
     (happy path) and is MEMORIZED (the Arabic normalizer works end-to-end —
     the ISS-133 catastrophe is gone).
  2. When the model chain is exhausted (all attempts fail), the SAME Arabic
     question in the SAME context is answered from the cognitive cache
     (resilience recall) instead of the "لا يجيب" safety-net stub — i.e. the
     system "answers every question".
  3. The Prometheus counters (`cogniforge_cognitive_cache_*`) increment.

Run:
    export OPENROUTER_API_KEY=sk-or-...
    python3 scripts/verify_cache_revolution_live.py

Exit codes: 0 = all live assertions passed, 1 = a failure, 2 = no API key.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Keep settings importable in a degraded sandbox (no real DB needed for the cache).
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "live-e2e-cache-secret-key-long-enough")
os.environ.setdefault("COGNITIVE_CACHE_RESILIENCE_ENABLED", "1")

from app.core.cognitive_cache import get_cognitive_engine
from app.core.gateway.simple_client import OpenRouterClient, SimpleAIClient
from app.core.types import JSONDict

_QUESTION = "اشرح باختصار ما هو التكامل في الرياضيات؟"
_ARABIC_RANGE = range(0x0600, 0x06FF + 1)


def _has_arabic(text: str) -> bool:
    return any(ord(ch) in _ARABIC_RANGE for ch in text)


def _content_of(chunks: list[JSONDict]) -> str:
    out = []
    for c in chunks:
        for choice in c.get("choices", []) or []:
            delta = choice.get("delta", {}) or {}
            if delta.get("content"):
                out.append(str(delta["content"]))
    return "".join(out)


def _metric_value(name: str, **labels: str) -> float:
    try:
        from prometheus_client import REGISTRY

        return REGISTRY.get_sample_value(name, labels or None) or 0.0
    except Exception:
        return 0.0


async def _stream(client: OpenRouterClient, question: str) -> list[JSONDict]:
    messages: list[JSONDict] = [{"role": "user", "content": question}]
    return [chunk async for chunk in client.stream_chat(messages)]


async def main() -> int:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("⏭️  SKIP: OPENROUTER_API_KEY not set — cannot run the live LLM path.")
        return 2

    engine = get_cognitive_engine()  # module singleton (shared across clients)
    ctx = SimpleAIClient()._get_context_hash([{"role": "user", "content": _QUESTION}])

    # ── 1. Happy path: real model → real Arabic answer → memorized ──────────
    print("① Live model call (real OpenRouter)…")
    live = SimpleAIClient()  # wires real config + shared cognitive engine
    chunks = await _stream(live, _QUESTION)
    answer = _content_of(chunks)
    print(f"   received {len(answer)} chars; arabic={_has_arabic(answer)}")
    assert answer.strip(), "FAIL: live model returned no content"
    assert _has_arabic(answer), "FAIL: answer is not Arabic"
    recalled = engine.recall(_QUESTION, ctx)
    assert recalled is not None, (
        "FAIL: successful turn was not memorized (Arabic normalize broken?)"
    )
    print("   ✅ answer is Arabic AND memorized (ISS-133 catastrophe gone)")

    # ── 2. Resilience: exhaust the chain → recall replays the cached answer ──
    print("② Forcing model-chain exhaustion (bogus model) + re-asking…")
    broken = OpenRouterClient(
        api_key=key,
        primary_model="invalid/nonexistent-model-xyz:free",
        fallback_models=["invalid/another-bogus-model:free"],
        cognitive_engine=engine,  # same singleton — holds the memorized answer
        safety_net=live.safety_net,
    )
    r_chunks = await _stream(broken, _QUESTION)
    r_answer = _content_of(r_chunks)
    served_from_cache = r_answer == _content_of(recalled)
    print(f"   received {len(r_answer)} chars; served_from_cache={served_from_cache}")
    assert served_from_cache, "FAIL: exhausted chain did NOT serve the cached answer"
    print("   ✅ resilience recall answered when every model failed")

    # ── 3. Metrics ─────────────────────────────────────────────────────────
    hits = _metric_value("cogniforge_cognitive_cache_recall_total", result="hit")
    mem = _metric_value("cogniforge_cognitive_cache_memorize_total")
    size = _metric_value("cogniforge_cognitive_cache_size")
    print(f"③ metrics: recall_hit={hits} memorize={mem} size={size}")
    assert hits >= 1, "FAIL: no recall hit recorded"
    assert mem >= 1, "FAIL: no memorize recorded"

    print("\n✅ LIVE E2E PASSED — cache revolution verified (D-180 / ISS-133).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
