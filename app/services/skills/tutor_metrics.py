"""
tutor_metrics — طبقة القياس السلوكي (Behavioral Measurement، D-131 §5).

حكم المالك (CTO-grade): «بلا قياس، الطبقات تبدو ذكية ولا تُخصِّص». هذه الوحدة تُصدِّر **المقاييس
الأربعة** التي تُثبت الأثر التعليمي الحقيقي قبل أي توسّع — تُغذّيها نقاط القرار القائمة (لا layer
جديد ثقيل) في `customer_chat` / `orchestrator_client`:

1. `cogniforge_tutor_repetition_avoided_total` — كم مرّة مُنعت إعادة طباعة/تكرار حرفي.
2. `cogniforge_tutor_definitional_answer_total{concept,resolved}` — سؤال تعريفي أُجيب فوراً أم لا.
3. `cogniforge_tutor_intervention_total{mtype}` — التدخّل مُصنَّف بنوع الاعتقاد الخاطئ (اختلاف التدخّلات).
4. `cogniforge_tutor_progress_total{outcome}` — تقدّم/تكرار/كشف بعد كل تفاعل.

كل الدوال fail-open (لا تكسر دور الطالب أبداً). كل مقياس له مُصدِر حيّ واحد على الأقل (§6.21).
"""

from __future__ import annotations

import contextlib

try:
    from prometheus_client import REGISTRY, Counter

    _existing = {m.name for m in REGISTRY.collect()}
    if "cogniforge_tutor_repetition_avoided" not in _existing:
        _REPETITION_AVOIDED = Counter(
            "cogniforge_tutor_repetition_avoided_total",
            "Times a literal re-print / repetition was avoided (D-130 + semantic layer).",
        )
        _DEFINITIONAL_ANSWER = Counter(
            "cogniforge_tutor_definitional_answer_total",
            "Definitional questions answered immediately (resolved) or not.",
            ["concept", "source", "resolved"],
        )
        _INTERVENTION = Counter(
            "cogniforge_tutor_intervention_total",
            "Interventions delivered, labelled by misconception type.",
            ["mtype"],
        )
        _PROGRESS = Counter(
            "cogniforge_tutor_progress_total",
            "Pedagogical outcome per interaction.",
            ["outcome"],
        )
    else:  # pragma: no cover — re-import in same process (tests)
        _REPETITION_AVOIDED = None  # type: ignore[assignment]
        _DEFINITIONAL_ANSWER = None  # type: ignore[assignment]
        _INTERVENTION = None  # type: ignore[assignment]
        _PROGRESS = None  # type: ignore[assignment]

    def record_repetition_avoided() -> None:
        """قياس 1: تراجع التكرار الحرفي."""
        with contextlib.suppress(Exception):
            if _REPETITION_AVOIDED is not None:
                _REPETITION_AVOIDED.inc()

    def record_definitional_answer(
        concept: str, resolved: bool, source: str = "deterministic"
    ) -> None:
        """قياس 2: سؤال تعريفي أُجيب بتعريف فوري (resolved=true) أم سقط.

        D-132: ``source`` (deterministic | llm) — ``llm`` يقيس **جاهزية الأسئلة الجديدة**.
        """
        with contextlib.suppress(Exception):
            if _DEFINITIONAL_ANSWER is not None:
                _DEFINITIONAL_ANSWER.labels(
                    concept=concept or "unknown",
                    source=source or "deterministic",
                    resolved=str(bool(resolved)).lower(),
                ).inc()

    def record_intervention(mtype: str) -> None:
        """قياس 3: التدخّل مُصنَّف بنوع الاعتقاد الخاطئ (اختلاف التدخّلات)."""
        with contextlib.suppress(Exception):
            if _INTERVENTION is not None:
                _INTERVENTION.labels(mtype=mtype or "unknown").inc()

    def record_progress(outcome: str) -> None:
        """قياس 4: ``outcome ∈ {advanced, repeated, revealed}`` — التقدّم بعد كل تفاعل."""
        with contextlib.suppress(Exception):
            if _PROGRESS is not None:
                _PROGRESS.labels(outcome=outcome or "unknown").inc()

except Exception:  # pragma: no cover — prometheus غير متوفّر (sandbox)

    def record_repetition_avoided() -> None:
        pass

    def record_definitional_answer(
        concept: str, resolved: bool, source: str = "deterministic"
    ) -> None:
        pass

    def record_intervention(mtype: str) -> None:
        pass

    def record_progress(outcome: str) -> None:
        pass


__all__ = [
    "record_definitional_answer",
    "record_intervention",
    "record_progress",
    "record_repetition_avoided",
]
