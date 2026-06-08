"""
اختبارات انحدار: التعرّف على التمرين صامد أمام أداة التعريف «ال» وتنويع الصياغة.

السبب الجذري (مُصلَح): عند «أعطني تمرين الأعداد المركبة 2024» كانت أداة استخراج
الموضوع تفشل لأن «أعداد مركبة» لا تطابق «الأعداد المركبة» (بادئة «ال»)، فيتعادل
تمرينا 2024 على السنة فقط ويفوز الاحتمالات بترتيب القائمة → يظهر تمرين خاطئ.

هذه الاختبارات تُثبت أن كل واحد من التمارين الثلاثة يُسترجَع بدقة عبر صياغات كثيرة
(عربي ±ال، ±سنة، ±رقم تمرين، فرنسي، إنجليزي). تُكمِّل
tests/contracts/test_four_fatal_bugs_regression.py (الذي يغطّي «أعداد مركبة» بلا ال).
"""

from __future__ import annotations

import pytest

from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    detect_exercise_retrieval,
    format_exercise_for_display,
    load_exercise_content,
)


class TestDefiniteArticleRecognition:
    """مصفوفة تعرّف شاملة: 3 تمارين × صياغات متعددة → التمرين الصحيح."""

    @pytest.mark.parametrize(
        ("query", "expected_exercise_number", "expected_year"),
        [
            # ── الأعداد المركبة (التمرين الثاني 2024) — قلب الكارثة ──
            ("أعطني تمرين الأعداد المركبة 2024", 2, 2024),  # مع «ال» + سنة (البق الأصلي)
            ("اعطني تمرين الأعداد المركبة", 2, 2024),  # مع «ال» بلا سنة
            ("اعطني تمرين أعداد مركبة 2024", 2, 2024),  # بلا «ال» (التغطية القديمة)
            ("أريد تمرين الأعداد المركبة من بكالوريا 2024", 2, 2024),
            ("complex numbers exercise 2024", 2, 2024),
            ("nombres complexes 2024", 2, 2024),
            ("الموضوع الأول 2024 التمرين الثاني", 2, 2024),
            # ── الاحتمالات (التمرين الأول 2024) ──
            ("تمرين الاحتمالات 2024", 1, 2024),
            ("أعطني تمرين الاحتمالات", 1, 2024),
            ("probability exercise 2024", 1, 2024),
            # ── الدوال العددية (التمرين الرابع 2016) ──
            ("اعطني تمرين الدوال العددية 2016", 4, 2016),
            ("تمرين الدوال العددية", 4, 2016),
            ("numerical functions exercise", 4, 2016),
        ],
    )
    def test_recognition_matrix(
        self, query: str, expected_exercise_number: int, expected_year: int
    ) -> None:
        decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=query))
        assert decision.recognized, f"لم يُتعرَّف على نية الاسترجاع لـ {query!r}"
        assert decision.matched_entry is not None, f"لا تطابق مُفهرَس لـ {query!r}"
        assert decision.matched_entry.exercise_number == expected_exercise_number, (
            f"{query!r} → تمرين #{decision.matched_entry.exercise_number} "
            f"(المتوقع #{expected_exercise_number})"
        )
        assert decision.matched_entry.year == expected_year

    def test_complex_with_definite_article_never_returns_probability(self) -> None:
        """القلب: «الأعداد المركبة» (مع ال + سنة) لا يُرجع تمرين الاحتمالات أبداً."""
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question="أعطني تمرين الأعداد المركبة 2024")
        )
        assert decision.recognized
        assert decision.matched_entry is not None
        # التمرين الثاني (الأعداد المركبة) — ليس الأول (الاحتمالات)
        assert decision.matched_entry.exercise_number == 2
        assert "الأعداد المركبة" in decision.matched_entry.topics

        # وعند العرض: لا يتسرّب نص الاحتمالات (الكرات)
        raw = load_exercise_content(decision.matched_entry)
        assert raw is not None
        formatted = format_exercise_for_display(decision.matched_entry, raw)
        assert "## التمرين الأول" not in formatted
        assert "كرة متماثلة" not in formatted
        assert "الأعداد المركبة" in formatted

    def test_probability_with_definite_article_returns_probability(self) -> None:
        """«الاحتمالات» (مع ال + سنة) يُرجع التمرين الأول."""
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question="أعطني تمرين الاحتمالات 2024")
        )
        assert decision.recognized
        assert decision.matched_entry is not None
        assert decision.matched_entry.exercise_number == 1
        assert "الاحتمالات" in decision.matched_entry.topics
