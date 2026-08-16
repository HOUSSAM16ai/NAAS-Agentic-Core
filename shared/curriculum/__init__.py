"""طبقة المنهاج — المصدر القانوني الوحيد لمفاهيم بكالوريا الجزائر (D-193)."""

from __future__ import annotations

from .registry import (
    CANONICAL_STREAMS,
    CANONICAL_SUBJECTS,
    CURRICULUM_REGISTRY,
    REGISTRY_VERSION,
    STREAM_COEFFICIENTS,
    SUBJECT_MARKERS,
    CurriculumConcept,
    CurriculumError,
    classify,
    classify_subject,
    concept,
    concepts_for_stream,
    exam_weight,
    label,
    next_concepts,
    prerequisites_of,
    resolve_alias,
    subject_coefficient,
)

__all__ = [
    "CANONICAL_STREAMS",
    "CANONICAL_SUBJECTS",
    "CURRICULUM_REGISTRY",
    "REGISTRY_VERSION",
    "STREAM_COEFFICIENTS",
    "SUBJECT_MARKERS",
    "CurriculumConcept",
    "CurriculumError",
    "classify",
    "classify_subject",
    "concept",
    "concepts_for_stream",
    "exam_weight",
    "label",
    "next_concepts",
    "prerequisites_of",
    "resolve_alias",
    "subject_coefficient",
]
