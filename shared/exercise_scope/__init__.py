"""الحزمة القانونية لنطاق التمرين — المصدر الوحيد لِـ«أيّ جزءٍ طلب الطالب؟» (D-206).

انظر `shared/exercise_scope/registry.py` للعقد الكامل وسبب وجوده (ISS-141).
"""

from __future__ import annotations

from shared.exercise_scope.registry import (
    EXPLANATION_CANCEL_MARKERS,
    ORDINAL_FORMS,
    PART_LABEL_MARKERS,
    SCOPE_ONLY_MARKERS,
    SCOPE_REQUEST_VERBS,
    ExerciseScope,
    ScopeSource,
    extract_target,
    ordinal_value,
    resolve_scope,
    strip_articles,
)

__all__ = [
    "EXPLANATION_CANCEL_MARKERS",
    "ORDINAL_FORMS",
    "PART_LABEL_MARKERS",
    "SCOPE_ONLY_MARKERS",
    "SCOPE_REQUEST_VERBS",
    "ExerciseScope",
    "ScopeSource",
    "extract_target",
    "ordinal_value",
    "resolve_scope",
    "strip_articles",
]
