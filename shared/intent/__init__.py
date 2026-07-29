"""`shared.intent` — المصدر القانوني الوحيد لنيّة الطالب (D-186).

انظر `shared/intent/registry.py` للعقد الكامل وسبب وجوده.
"""

from shared.intent.registry import (
    INTENT_REGISTRY,
    IntentEntry,
    all_intents,
    classify,
    markers_for,
    matches,
    normalize,
)

__all__ = [
    "INTENT_REGISTRY",
    "IntentEntry",
    "all_intents",
    "classify",
    "markers_for",
    "matches",
    "normalize",
]
