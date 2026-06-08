"""
اختبارات مُسترجِع تمارين البكالوريا من Supabase (bac_db_retriever).

تختبر المنطق النقي (استخراج الإشارات، بناء SQL، إعادة الترتيب) دون قاعدة بيانات.
الاستعلام الحي مقابل Supabase الحقيقي يُتحقَّق منه عبر الجسر (scripts) + Codespaces.

الوحدة نقية على مستوى الوحدة (stdlib + arabic_normalize) — sqlalchemy lazy داخل الدوال.
"""

from __future__ import annotations

import pytest

from app.services.capabilities.bac_db_retriever import (
    build_candidate_query,
    extract_db_facets,
    rerank_candidates,
)

# صفوف وهمية تحاكي bac_exercises (الـ 3 التمارين الحقيقية)
_ROWS: list[dict] = [
    {
        "id": "p",
        "topic": "Probability",
        "year": 2024,
        "exercise_number": 1,
        "raw_text": "التمرين الأول الاحتمالات كيس على 11 كرة",
        "exam_ref": "Subject 1",
        "session": "دورة 2024",
    },
    {
        "id": "c",
        "topic": "Complex Numbers",
        "year": 2024,
        "exercise_number": 2,
        "raw_text": "التمرين الثاني الأعداد المركبة حل المعادلة z",
        "exam_ref": "Subject 1",
        "session": "دورة 2024",
    },
    {
        "id": "f",
        "topic": "Numerical Functions",
        "year": 2016,
        "exercise_number": 4,
        "raw_text": "التمرين الرابع الدوال العددية الدالة g",
        "exam_ref": "Subject 2",
        "session": "دورة 2016 الأولى",
    },
]


class TestExtractFacets:
    @pytest.mark.parametrize(
        ("query", "year", "canon_id"),
        [
            ("أعطني تمرين الأعداد المركبة 2024", 2024, "complex_numbers"),
            ("تمرين الاحتمالات 2024", 2024, "probability"),
            ("اعطني تمرين الدوال العددية 2016", 2016, "numerical_functions"),
            ("تمرين الأعداد المركبة", None, "complex_numbers"),
        ],
    )
    def test_facets(self, query: str, year: int | None, canon_id: str) -> None:
        f = extract_db_facets(query)
        assert f.year == year
        assert f.canonical is not None
        assert f.canonical.canonical_id == canon_id
        assert f.is_anchored

    def test_year_2016_included(self) -> None:
        # حارس ضد ثغرة 20[2-3]\\d التي كانت تُسقط 2016
        assert extract_db_facets("امتحان 2016").year == 2016

    def test_exercise_number(self) -> None:
        assert extract_db_facets("التمرين الثاني 2024").exercise_number == 2
        assert extract_db_facets("exercise 4").exercise_number == 4

    def test_unanchored(self) -> None:
        assert not extract_db_facets("مرحبا").is_anchored


class TestBuildQuery:
    def test_complex_query_params(self) -> None:
        f = extract_db_facets("تمرين الأعداد المركبة 2024")
        sql, params = build_candidate_query(f)
        assert "FROM bac_exercises" in sql
        assert "LIMIT" in sql
        assert params["year"] == 2024
        assert params["canon_like"] == "%complex%"
        # raw_text العربي المميِّز ضمن المعاملات
        assert any("الأعداد المركبة" in str(v) for v in params.values())

    def test_parametrized_not_interpolated(self) -> None:
        # حماية حقن: القيم تُمرَّر كمعاملات لا تُحقَن في نص SQL
        f = extract_db_facets("تمرين الاحتمالات 2024")
        sql, _ = build_candidate_query(f)
        assert ":year" in sql
        assert "2024" not in sql  # القيمة في params لا في النص


class TestRerank:
    @pytest.mark.parametrize(
        ("query", "expected_topic", "expected_ex"),
        [
            ("أعطني تمرين الأعداد المركبة 2024", "Complex Numbers", 2),
            ("تمرين الاحتمالات 2024", "Probability", 1),
            ("اعطني تمرين الدوال العددية 2016", "Numerical Functions", 4),
            ("تمرين الأعداد المركبة", "Complex Numbers", 2),
        ],
    )
    def test_rerank_picks_correct(self, query: str, expected_topic: str, expected_ex: int) -> None:
        f = extract_db_facets(query)
        match = rerank_candidates(_ROWS, f)
        assert match is not None
        assert match.topic == expected_topic
        assert match.exercise_number == expected_ex

    def test_complex_query_never_returns_probability(self) -> None:
        # القلب: استعلام الأعداد المركبة لا يُرجع الاحتمالات أبداً
        f = extract_db_facets("أعطني تمرين الأعداد المركبة 2024")
        match = rerank_candidates(_ROWS, f)
        assert match is not None
        assert match.topic != "Probability"
        assert match.canonical_id == "complex_numbers"

    def test_empty_rows(self) -> None:
        f = extract_db_facets("تمرين الأعداد المركبة 2024")
        assert rerank_candidates([], f) is None

    def test_deterministic_no_list_order_dependence(self) -> None:
        # عكس ترتيب الصفوف يجب ألا يغيّر النتيجة (كسر التعادل حتمي)
        f = extract_db_facets("تمرين الاحتمالات 2024")
        forward = rerank_candidates(_ROWS, f)
        backward = rerank_candidates(list(reversed(_ROWS)), f)
        assert forward is not None and backward is not None
        assert forward.exercise_id == backward.exercise_id
