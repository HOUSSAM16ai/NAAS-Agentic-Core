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
    from prometheus_client import REGISTRY, Counter, Histogram

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
        # D-133: قراءة حالة الطالب — يُثبت أن الـ label غيّر نوع الرد (لا تصنيف فقط).
        _INTENT = Counter(
            "cogniforge_tutor_intent_total",
            "Student-intent reads, labelled by primary intent.",
            ["primary"],
        )
        _FRUSTRATION = Counter(
            "cogniforge_tutor_frustration_total",
            "Transient frustration level per interaction (D-133).",
            ["level"],
        )
        _RESPONSE_MODE = Counter(
            "cogniforge_tutor_response_mode_total",
            "Chosen response mode per interaction — proves intent changed the pedagogy.",
            ["mode"],
        )
        # D-135: حالة الفهم لكل مكوّن معرفي — يقيس الإتقان المستقلّ (لا جمال الحوار).
        _UNDERSTANDING = Counter(
            "cogniforge_tutor_understanding_total",
            "Per-knowledge-component understanding state (Learning State, D-135).",
            ["kc", "state"],
        )
        # D-138: المصفوفة التصعيدية — يقيس **تدرّج الرُّتب** (تعريف→مثال→محاكاة)، الأثر السلوكي.
        _ESCALATION = Counter(
            "cogniforge_tutor_escalation_total",
            "Pedagogical escalation decisions, labelled by concept + strategy level (D-138).",
            ["concept", "level"],
        )
        _MICRO_SIMULATION = Counter(
            "cogniforge_tutor_micro_simulation_total",
            "Deterministic micro-simulations served (L3 content), labelled by concept (D-138).",
            ["concept"],
        )
        # D-143: بوّابة قياس توجيه الاحتمالات — يُثبت أن الحدث الصحيح أُجيب (لا انحراف لـ A،
        # لا تكرار). outcome ∈ {correct_event, deferred, drifted_to_a, repeated}.
        _PROB_ROUTING = Counter(
            "cogniforge_tutor_routing_total",
            "Probability sub-question routing outcome per event (D-143 measurement gate).",
            ["event", "outcome"],
        )
        # D-157 (M9 — النجم القطبي §0.6): فجوة الوهم + القناتان. المقياس الوحيد
        # للنجاح يُبَثّ أخيراً (كان يُحسَب ويُسجَّل في اللوغ فقط بلا رصد).
        _ILLUSION_GAP = Histogram(
            "cogniforge_tutor_illusion_gap",
            "Illusion gap = assisted − durable mastery per interaction (§0.6 north star).",
            buckets=(0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0),
        )
        _ASSISTED_MASTERY = Histogram(
            "cogniforge_tutor_assisted_mastery",
            "Assisted mastery probability per interaction (scaffold-inflated channel).",
            buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
        )
        _DURABLE_MASTERY = Histogram(
            "cogniforge_tutor_durable_mastery",
            "Durable (honest) mastery probability per interaction — forgetting-curve channel.",
            buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
        )
        _DURABLE_RISE = Counter(
            "cogniforge_tutor_durable_rise_total",
            "Durable-mastery rise events, labelled by cause (D-157).",
            ["cause"],
        )
    else:  # pragma: no cover — re-import in same process (tests)
        _REPETITION_AVOIDED = None  # type: ignore[assignment]
        _DEFINITIONAL_ANSWER = None  # type: ignore[assignment]
        _INTERVENTION = None  # type: ignore[assignment]
        _PROGRESS = None  # type: ignore[assignment]
        _INTENT = None  # type: ignore[assignment]
        _FRUSTRATION = None  # type: ignore[assignment]
        _RESPONSE_MODE = None  # type: ignore[assignment]
        _UNDERSTANDING = None  # type: ignore[assignment]
        _ESCALATION = None  # type: ignore[assignment]
        _MICRO_SIMULATION = None  # type: ignore[assignment]
        _PROB_ROUTING = None  # type: ignore[assignment]
        _ILLUSION_GAP = None  # type: ignore[assignment]
        _ASSISTED_MASTERY = None  # type: ignore[assignment]
        _DURABLE_MASTERY = None  # type: ignore[assignment]
        _DURABLE_RISE = None  # type: ignore[assignment]

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

    def record_intent(primary: str) -> None:
        """D-133: توزيع النيّة الأساسية المُلتقَطة (confusion/example_request/procedure/...)."""
        with contextlib.suppress(Exception):
            if _INTENT is not None:
                _INTENT.labels(primary=primary or "unknown").inc()

    def record_frustration(level: str) -> None:
        """D-133: حالة الإحباط اللحظية (none/low/medium/high)."""
        with contextlib.suppress(Exception):
            if _FRUSTRATION is not None:
                _FRUSTRATION.labels(level=level or "none").inc()

    def record_response_mode(mode: str) -> None:
        """D-133: نوع الرد المُختار — يُثبت أن الـ label أنتج بيداغوجيا مغايرة."""
        with contextlib.suppress(Exception):
            if _RESPONSE_MODE is not None:
                _RESPONSE_MODE.labels(mode=mode or "unknown").inc()

    def record_understanding(kc: str, state: str) -> None:
        """D-135: حالة فهم مكوّن معرفي (not_addressed/explained/understood) — قياس الإتقان."""
        with contextlib.suppress(Exception):
            if _UNDERSTANDING is not None:
                _UNDERSTANDING.labels(kc=kc or "unknown", state=state or "unknown").inc()

    def record_escalation(concept: str, level: str) -> None:
        """D-138: قرار تصعيد بيداغوجي (concept + level) — يُثبت تدرّج الرُّتب (لا تكرار)."""
        with contextlib.suppress(Exception):
            if _ESCALATION is not None:
                _ESCALATION.labels(concept=concept or "unknown", level=level or "unknown").inc()

    def record_micro_simulation(concept: str) -> None:
        """D-138: محاكاة مصغّرة حتمية قُدِّمت (محتوى L3)، مُصنَّفة بالمفهوم."""
        with contextlib.suppress(Exception):
            if _MICRO_SIMULATION is not None:
                _MICRO_SIMULATION.labels(concept=concept or "unknown").inc()

    def record_probability_routing(event: str, outcome: str) -> None:
        """D-143: نتيجة توجيه سؤال احتمالي. outcome ∈ {correct_event,deferred,drifted_to_a,repeated}."""
        with contextlib.suppress(Exception):
            if _PROB_ROUTING is not None:
                _PROB_ROUTING.labels(event=event or "unknown", outcome=outcome or "unknown").inc()

    def record_illusion_gap(gap: float) -> None:
        """D-157 (M9): فجوة الوهم لكل تفاعل — المقياس الوحيد للنجاح (§0.6)."""
        with contextlib.suppress(Exception):
            if _ILLUSION_GAP is not None:
                _ILLUSION_GAP.observe(max(0.0, min(1.0, float(gap))))

    def record_mastery_channels(assisted: float, durable: float) -> None:
        """D-157 (M9): توزيع القناتين (المدعوم مقابل الدائم الصادق) لكل تفاعل."""
        with contextlib.suppress(Exception):
            if _ASSISTED_MASTERY is not None:
                _ASSISTED_MASTERY.observe(max(0.0, min(1.0, float(assisted))))
            if _DURABLE_MASTERY is not None:
                _DURABLE_MASTERY.observe(max(0.0, min(1.0, float(durable))))

    def record_durable_rise(cause: str) -> None:
        """D-157 (M9): حدث ارتفاع الإتقان الدائم. cause ∈ {unaided_delayed_novel,retest,none}."""
        with contextlib.suppress(Exception):
            if _DURABLE_RISE is not None:
                _DURABLE_RISE.labels(cause=cause or "none").inc()

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

    def record_intent(primary: str) -> None:
        pass

    def record_frustration(level: str) -> None:
        pass

    def record_response_mode(mode: str) -> None:
        pass

    def record_understanding(kc: str, state: str) -> None:
        pass

    def record_escalation(concept: str, level: str) -> None:
        pass

    def record_micro_simulation(concept: str) -> None:
        pass

    def record_probability_routing(event: str, outcome: str) -> None:
        pass

    def record_illusion_gap(gap: float) -> None:
        pass

    def record_mastery_channels(assisted: float, durable: float) -> None:
        pass

    def record_durable_rise(cause: str) -> None:
        pass


__all__ = [
    "record_definitional_answer",
    "record_durable_rise",
    "record_escalation",
    "record_frustration",
    "record_illusion_gap",
    "record_intent",
    "record_intervention",
    "record_mastery_channels",
    "record_micro_simulation",
    "record_probability_routing",
    "record_progress",
    "record_repetition_avoided",
    "record_response_mode",
    "record_understanding",
]
