"""Arabic-first cognitive cache — regression suite (D-180 / ISS-133).

The V1 ``CognitiveResonanceEngine`` normalized prompts with ``[^a-z0-9\\s]``,
which strips every Arabic character on an Arabic BAC platform → recall/memorize
were silent no-ops. These tests lock the Arabic-aware behavior in place:

* Arabic prompts tokenize to a non-empty set.
* memorize → recall round-trips for Arabic (including diacritics / alef / teh
  marbuta variants that must resonate as the same question).
* ``context_hash`` isolates different pedagogical states.
* TTL expiry and the resonance threshold still behave.
* English still works (no regression).
"""

from __future__ import annotations

import time

import pytest

from app.core import cognitive_cache
from app.core.cognitive_cache import (
    CognitiveResonanceEngine,
    SemanticEngram,
    get_cognitive_engine,
)

_CHUNK = [{"choices": [{"delta": {"content": "المشتقة هي cos(x)"}}]}]


@pytest.fixture
def engine() -> CognitiveResonanceEngine:
    return CognitiveResonanceEngine()


def test_arabic_prompt_tokenizes_non_empty(engine: CognitiveResonanceEngine) -> None:
    tokens = engine._normalize("ما هو تكامل الدالة x^2 ؟")
    assert tokens, "Arabic prompt must not normalize to an empty token set"
    # Punctuation is stripped but Arabic words + digits survive.
    assert "تكامل" in tokens
    assert "x" in tokens
    assert "2" in tokens


def test_diacritics_and_alef_variants_resonate(engine: CognitiveResonanceEngine) -> None:
    ctx = "ctx-derivative"
    engine.memorize("كيف أحسب مشتقة الدالة sin(x)", ctx, _CHUNK)
    # Different diacritics + alef/hamza form of the SAME question must hit.
    recalled = engine.recall("كيف احسب مُشتقة الدالة sin(x)", ctx)
    assert recalled == _CHUNK


def test_teh_marbuta_normalized(engine: CognitiveResonanceEngine) -> None:
    # الدالة (with ة) and الداله (with ه) must fold to the same token.
    assert engine._normalize("الدالة") == engine._normalize("الداله")


def test_context_hash_isolation(engine: CognitiveResonanceEngine) -> None:
    engine.memorize("كيف أحسب مشتقة الدالة sin(x)", "ctx-a", _CHUNK)
    # Same prompt, different context = different universe → miss.
    assert engine.recall("كيف أحسب مشتقة الدالة sin(x)", "ctx-b") is None


def test_ttl_expiry(monkeypatch: pytest.MonkeyPatch, engine: CognitiveResonanceEngine) -> None:
    ctx = "ctx-ttl"
    engine.memorize("ما هي قاعدة السلسلة", ctx, _CHUNK)
    assert engine.recall("ما هي قاعدة السلسلة", ctx) == _CHUNK
    # Fast-forward past CACHE_TTL → engram is expired and skipped.
    # Capture real time FIRST so the patched clock isn't self-referential.
    future = time.time() + cognitive_cache.CACHE_TTL + 10
    monkeypatch.setattr(cognitive_cache.time, "time", lambda: future)
    assert engine.recall("ما هي قاعدة السلسلة", ctx) is None


def test_low_resonance_below_threshold_misses(engine: CognitiveResonanceEngine) -> None:
    engine.memorize("كيف أحسب مشتقة الدالة sin(x)", "ctx", _CHUNK)
    # Completely unrelated Arabic question → below RESONANCE_THRESHOLD → miss.
    assert engine.recall("ما هي عاصمة الجزائر", "ctx") is None


def test_empty_after_normalization_is_miss(engine: CognitiveResonanceEngine) -> None:
    # Punctuation-only prompt normalizes to empty → recall short-circuits to miss.
    assert engine.recall("؟؟؟ !!!", "ctx") is None


def test_english_regression_still_works(engine: CognitiveResonanceEngine) -> None:
    ctx = "ctx-en"
    engine.memorize("what is the integral of x squared", ctx, _CHUNK)
    assert engine.recall("what is the integral of x squared", ctx) == _CHUNK
    # Stop words are filtered but content words survive.
    tokens = engine._normalize("what is the integral of x")
    assert "integral" in tokens
    assert "the" not in tokens


def test_stats_track_hits_and_misses(engine: CognitiveResonanceEngine) -> None:
    ctx = "ctx-stats"
    engine.memorize("سؤال تجريبي", ctx, _CHUNK)
    engine.recall("سؤال تجريبي", ctx)  # hit
    engine.recall("سؤال غير موجود إطلاقا هنا", ctx)  # miss
    stats = engine.get_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    assert stats["memory_usage"] == 1


def test_get_cognitive_engine_returns_real_singleton() -> None:
    # D-180: the long-standing "returns None / stub" claim was false.
    engine = get_cognitive_engine()
    assert isinstance(engine, CognitiveResonanceEngine)
    assert get_cognitive_engine() is engine  # stable singleton


def test_semantic_engram_expiry_flag() -> None:
    fresh = SemanticEngram(
        original_prompt="p", context_hash="c", normalized_tokens={"p"}, response_payload=_CHUNK
    )
    assert fresh.is_expired is False
