"""Shard: Indexed retrieval preempt decisions (D-256).

**لماذا هذه الشريحة موجودة (CodeScene X-Ray — job 72):** كان `_has_indexed_match`
أعلى دالة ترددًا في `orchestrator_client.py` (churn=2 · 38 سطرًا) وتحمل embedded import
(استيراد `bac_db_retriever.extract_db_facets` داخل body) مع `try/except` واسع
يلتقط كل شيء — تركيزٌ بنيوي مخالف لعقيدة الشرائح النقية (لا استيراد داخل الوظائف،
مسار فشل صريح قابل للاختبار). فُكِّك إلى `resolve_indexed_anchor` نقية تعزل قرار
Supabase في شريحةٍ مستقلة، و`_has_indexed_match` في القشرة صار ثلاثية تفويض.
"""

from __future__ import annotations

import dataclasses

from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    detect_exercise_retrieval,
    detect_explanation_with_context,
)


@dataclasses.dataclass(frozen=True)
class IndexedMatchDecision:
    """قرار تطابق الاسترجاع المفهرَس (بيانات معلنة — نمط D-249)."""

    recognized: bool
    matched_entry: object | None
    db_anchored: bool


def resolve_indexed_anchor(
    question: str,
    history_messages: list[dict[str, str]] | None = None,
) -> IndexedMatchDecision:
    """يفصل قرار «تجاوز orchestrator والـ StateGraph» إلى خطواتٍ نقية قابلة للاختبار.

    ISS-056 (D-049 — Indexed Retrieval Preemption Doctrine): المطابقة المفهرَسة
    المؤكدة ⇒ preempt فوري (لا HTTP roundtrip · لا LLM call). وإن كانت نية
    الاسترجاع مؤكدة بلا تطابق محلي لكن بإشارةٍ بنيوية ⇒ نجرّب المسار القابل
    للتوسع (Supabase) — وإن فشل فالبث الفارغ يسقط للمسار العادي.
    """
    decision = detect_exercise_retrieval(
        ExerciseRetrievalRequest(question=question),
        history_messages=history_messages,
    )
    if not decision.recognized:
        return IndexedMatchDecision(recognized=False, matched_entry=None, db_anchored=False)
    if decision.matched_entry is not None:
        # السلوك الأصلي: matched_entry ⇒ True فوري (بدون محاولة Supabase)
        return IndexedMatchDecision(
            recognized=True, matched_entry=decision.matched_entry, db_anchored=True
        )
    # المسار القابل للتوسع: نية استرجاع + إشارة بنيوية ⇒ نجرّب Supabase.
    try:
        from app.services.capabilities.bac_db_retriever import extract_db_facets

        is_anchored = extract_db_facets(question).is_anchored
    except Exception:
        is_anchored = False
    return IndexedMatchDecision(recognized=True, matched_entry=None, db_anchored=is_anchored)


def resolve_explanation_with_context(
    question: str,
    history_messages: list[dict[str, str]] | None,
) -> bool:
    """يكشف طلب شرحٍ مرتبط بسياق تمرين بكالوريا (ISS-058 / D-052 — قشرة تفويض).

    عند الانطباق نجتاز orchestrator-service بالكامل لمنع: dump عدة تمارين غير
    متعلقة · تسريب tags مثل [ex: ex_1] · هلوسة LLM بسبب سياقٍ واسع غير متعلق.
    """
    decision = detect_explanation_with_context(
        ExerciseRetrievalRequest(question=question),
        history_messages=history_messages,
    )
    return decision.recognized and decision.matched_entry is not None
