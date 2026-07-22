# app/core/cognitive_cache.py
"""
THE COGNITIVE RESONANCE ENGINE (V1 - OMEGA).

This module implements a "Hyper-Dimensional Semantic Cache" that transcends
traditional exact-match caching. It utilizes "Resonance Algorithms" to detect
semantic similarity between queries, allowing the system to recall answers
to questions that are "spiritually identical" even if syntactically different.

TECHNOLOGIES:
- Token-Set Holography (Jaccard Similarity on N-grams).
- Structural Echo Detection (Sequence Matching).
- Adaptive Resonance Thresholding.
"""

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

# --- Configuration ---
RESONANCE_THRESHOLD = 0.60  # Tuned for high-recall in V1 (Caveman-speak compatibility)
CACHE_TTL = 3600  # 1 Hour
MAX_MEMORY_SLOTS = 1000  # Max number of semantic patterns to hold

# --- Arabic normalization (D-180 / ISS-133) ---
# The V1 engine normalized with ``[^a-z0-9\s]`` which strips EVERY Arabic
# character — on an Arabic BAC platform that made recall/memorize a silent
# no-op. We now normalize Unicode-aware: strip tashkeel + tatweel, unify the
# alef / teh-marbuta / alef-maqsura variants, then keep word chars via ``\w``
# (Python ``re`` is Unicode-aware for ``str``) so Arabic, French and English
# all tokenize correctly.
_ARABIC_DIACRITICS = re.compile(r"[ً-ٰٟـ]")  # tashkeel + tatweel
_ARABIC_NORMALIZE_MAP = str.maketrans(
    {
        "آ": "ا",  # آ → ا
        "أ": "ا",  # أ → ا
        "إ": "ا",  # إ → ا
        "ٱ": "ا",  # ٱ → ا
        "ة": "ه",  # ة → ه
        "ى": "ي",  # ى → ي
    }
)
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)

# Bilingual stop-word set. Kept modest so we never over-normalize distinct
# questions into the same token bag.
_STOP_WORDS = frozenset(
    {
        # English
        "the",
        "is",
        "at",
        "which",
        "on",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        # Arabic function words
        "من",
        "في",
        "على",
        "الى",
        "إلى",
        "عن",
        "ما",
        "هل",
        "هذا",
        "هذه",
        "ذلك",
        "التي",
        "الذي",
        "مع",
        "كل",
        "عند",
        "او",
        "أو",
        "ثم",
        "قد",
        "كان",
        "هو",
        "هي",
        "ان",
        "أن",
        "إن",
    }
)


def _cache_counter(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Any:
    """Re-import-safe Prometheus ``Counter`` on the default REGISTRY (D-180).

    Mirrors ``app/services/skills/base.py:skill_counter`` but is inlined here so
    ``app/core`` stays self-contained (no core→services import) and never raises
    when ``prometheus_client`` is absent (returns a no-op).
    """
    return _metric_factory("Counter", name, documentation, labelnames)


def _cache_histogram(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Any:
    """Re-import-safe Prometheus ``Histogram`` on the default REGISTRY (D-180)."""
    return _metric_factory("Histogram", name, documentation, labelnames)


def _cache_gauge(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Any:
    """Re-import-safe Prometheus ``Gauge`` on the default REGISTRY (D-180)."""
    return _metric_factory("Gauge", name, documentation, labelnames)


class _NoopMetric:
    """No-op metric used when prometheus is unavailable or registration fails."""

    def labels(self, *args: Any, **kwargs: Any) -> "_NoopMetric":
        return self

    def inc(self, *args: Any, **kwargs: Any) -> None:
        return None

    def observe(self, *args: Any, **kwargs: Any) -> None:
        return None

    def set(self, *args: Any, **kwargs: Any) -> None:
        return None


def _metric_factory(kind: str, name: str, documentation: str, labelnames: tuple[str, ...]) -> Any:
    try:
        import prometheus_client
        from prometheus_client import REGISTRY
    except Exception:  # pragma: no cover - prometheus not installed
        return _NoopMetric()
    try:
        cls = getattr(prometheus_client, kind)
        return cls(name, documentation, list(labelnames))
    except ValueError:
        # Already registered (common under test re-import): reuse the collector.
        mapping = getattr(REGISTRY, "_names_to_collectors", {})
        for key in (name, f"{name}_total", name.removesuffix("_total")):
            collector = mapping.get(key)
            if collector is not None:
                return collector
        return _NoopMetric()


# Module-level singletons (registered once; re-import safe).
_RECALL_TOTAL = _cache_counter(
    "cogniforge_cognitive_cache_recall_total",
    "Cognitive cache recall attempts by result (hit|miss).",
    ("result",),
)
_MEMORIZE_TOTAL = _cache_counter(
    "cogniforge_cognitive_cache_memorize_total",
    "Cognitive cache memorize (store) operations.",
)
_RESONANCE_SCORE = _cache_histogram(
    "cogniforge_cognitive_cache_resonance_score",
    "Best resonance score observed per recall attempt.",
)
_CACHE_SIZE = _cache_gauge(
    "cogniforge_cognitive_cache_size",
    "Number of semantic engrams currently held in the cognitive cache.",
)


@dataclass
class SemanticEngram:
    """
    Represents a stored memory pattern in the Cognitive Cache.
    """

    original_prompt: str
    context_hash: str  # Hash of the conversation history to ensure context safety
    normalized_tokens: set[str]
    response_payload: list[dict]  # The full chat history or response chunks
    created_at: float = field(default_factory=time.time)
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > CACHE_TTL


class CognitiveResonanceEngine:
    """
    The Brain that remembers.
    Implements fuzzy semantic matching without heavy ML dependencies.
    """

    def __init__(self):
        self.memory: deque[SemanticEngram] = deque(maxlen=MAX_MEMORY_SLOTS)
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _normalize(self, text: str) -> set[str]:
        """
        Reduces text to its atomic semantic tokens — Arabic-first (D-180 / ISS-133).

        Pipeline:
        1. Lowercase (safe for Latin; a no-op for Arabic letters).
        2. Strip Arabic tashkeel (diacritics) and tatweel.
        3. Unify alef / teh-marbuta / alef-maqsura variants.
        4. Drop punctuation while KEEPING word chars via ``\\w`` (Unicode-aware),
           so Arabic/French/English all survive.
        5. Bilingual stop-word filtering.
        """
        text = text.lower()
        text = _ARABIC_DIACRITICS.sub("", text)
        text = text.translate(_ARABIC_NORMALIZE_MAP)
        # Keep letters/digits/underscore + whitespace; strip punctuation only.
        text = _NON_WORD.sub(" ", text)
        tokens = set(text.split())
        return tokens - _STOP_WORDS

    def _calculate_resonance(
        self, tokens_a: set[str], tokens_b: set[str], text_a: str, text_b: str
    ) -> float:
        """
        Calculates the "Resonance Score" (Similarity) between two inputs.
        Combines Token Overlap (Jaccard) with Structural Similarity.
        """
        if not tokens_a or not tokens_b:
            return 0.0

        # 1. Jaccard Similarity (Token Overlap)
        intersection = len(tokens_a.intersection(tokens_b))
        union = len(tokens_a.union(tokens_b))
        jaccard_score = intersection / union if union > 0 else 0.0

        # 2. Containment Bonus (If one is a subset of the other)
        # Helps with "tell joke computers" vs "tell me a joke about computers"
        min_len = min(len(tokens_a), len(tokens_b))
        containment_score = intersection / min_len if min_len > 0 else 0.0

        # 3. Structural Similarity (Sequence Matcher) - computationally more expensive but more accurate for order
        # We only run this if Jaccard is promising (> 0.3) to save CPU
        structural_score = 0.0
        if jaccard_score > 0.2:
            structural_score = SequenceMatcher(None, text_a, text_b).ratio()

        # Weighted Average:
        # Jaccard: 30%, Containment: 30%, Structure: 40%
        return (jaccard_score * 0.3) + (containment_score * 0.3) + (structural_score * 0.4)

    def _find_best_match(
        self, input_tokens: set[str], prompt: str, context_hash: str
    ) -> tuple[SemanticEngram | None, float]:
        """
        Scans memory for the most resonant engram.
        """
        best_engram = None
        best_score = 0.0

        # Linear scan of memory (acceptable for <1000 items).
        # For larger scales, we would use LSH (Locality Sensitive Hashing).
        for engram in self.memory:
            if engram.is_expired:
                continue

            # Strict Context Check: Different context = Different universe.
            if engram.context_hash != context_hash:
                continue

            score = self._calculate_resonance(
                input_tokens, engram.normalized_tokens, prompt, engram.original_prompt
            )

            if score > best_score:
                best_score = score
                best_engram = engram

        return best_engram, best_score

    def recall(self, prompt: str, context_hash: str) -> list[dict] | None:
        """
        Attempts to recall a memory that resonates with the input prompt.
        Must match context_hash exactly (Safety First!) but allows fuzzy match on prompt.
        """
        input_tokens = self._normalize(prompt)
        if not input_tokens:
            _RECALL_TOTAL.labels(result="miss").inc()
            return None

        best_engram, best_score = self._find_best_match(input_tokens, prompt, context_hash)
        _RESONANCE_SCORE.observe(best_score)

        if best_score >= RESONANCE_THRESHOLD and best_engram:
            logger.info(
                f"Cognitive Resonance Detected! Score: {best_score:.4f} | "
                f"Query: '{prompt}' matches '{best_engram.original_prompt}'"
            )
            best_engram.access_count += 1
            self._stats["hits"] += 1
            _RECALL_TOTAL.labels(result="hit").inc()
            return best_engram.response_payload

        self._stats["misses"] += 1
        _RECALL_TOTAL.labels(result="miss").inc()
        return None

    def memorize(self, prompt: str, context_hash: str, response: list[dict]) -> None:
        """
        Stores a new experience in the Cognitive Cache.
        """
        tokens = self._normalize(prompt)
        if not tokens:
            return

        engram = SemanticEngram(
            original_prompt=prompt,
            context_hash=context_hash,
            normalized_tokens=tokens,
            response_payload=response,
        )
        self.memory.appendleft(engram)  # MRU (Most Recently Used) logic via appendleft + maxlen
        _MEMORIZE_TOTAL.inc()
        _CACHE_SIZE.set(len(self.memory))
        logger.debug(f"Memorized new pattern: '{prompt[:30]}...'")

    def get_stats(self) -> dict[str, int]:
        return {**self._stats, "memory_usage": len(self.memory), "capacity": MAX_MEMORY_SLOTS}


# Singleton Instance
_cognitive_engine = CognitiveResonanceEngine()


def get_cognitive_engine() -> CognitiveResonanceEngine:
    return _cognitive_engine
