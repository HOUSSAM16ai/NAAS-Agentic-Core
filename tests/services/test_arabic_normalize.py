"""
اختبارات محرّك التطبيع والتعرّف العربي (arabic_normalize).

يحرس ضد عودة كارثة أداة التعريف «ال»: «الأعداد المركبة» يجب أن يطابق «أعداد مركبة»
بعد التطبيع، وإلا عاد استرجاع الاحتمالات بدل الأعداد المركبة.

الوحدة نقية (stdlib فقط) — لا تعتمد pydantic/قاعدة بيانات.
"""

from __future__ import annotations

import pytest

from app.services.capabilities.arabic_normalize import (
    CANONICAL_BY_ID,
    normalize_ar,
    normalize_tokens,
    primary_canonical_topic,
    resolve_canonical_topics,
)


class TestNormalizeAr:
    """تطبيع النص العربي الصرفي."""

    def test_definite_article_stripped(self) -> None:
        # القلب: «الأعداد المركبة» (مع ال) == «أعداد مركبة» (بدون ال)
        assert normalize_ar("الأعداد المركبة") == normalize_ar("أعداد مركبة")
        assert normalize_ar("الاحتمالات") == normalize_ar("احتمالات")
        assert normalize_ar("الدوال العددية") == normalize_ar("دوال عددية")

    def test_hamza_variants_unified(self) -> None:
        assert normalize_ar("أعداد") == normalize_ar("اعداد")
        assert normalize_ar("إجابة") == normalize_ar("اجابة")
        assert normalize_ar("آمن") == normalize_ar("امن")

    def test_taa_marbuta_and_alef_maqsura(self) -> None:
        assert normalize_ar("دالة") == normalize_ar("داله")
        assert normalize_ar("على") == normalize_ar("علي")

    def test_diacritics_and_tatweel_removed(self) -> None:
        assert normalize_ar("الْأَعْدَاد") == normalize_ar("الاعداد")
        assert normalize_ar("أعـــداد") == normalize_ar("أعداد")

    def test_arabic_indic_digits_folded(self) -> None:
        assert normalize_ar("٢٠٢٤") == "2024"

    def test_short_word_protection(self) -> None:
        # «والد» يجب ألا يُشوَّه إلى «د» (الجذع القصير محمي)
        assert "والد" in normalize_ar("والد فلاح").split()

    def test_empty_and_non_string(self) -> None:
        assert normalize_ar("") == ""
        assert normalize_ar("   ") == ""

    def test_idempotent(self) -> None:
        once = normalize_ar("الأعداد المركبة 2024")
        assert normalize_ar(once) == once


class TestNormalizeTokens:
    def test_token_set(self) -> None:
        toks = normalize_tokens("تمرين الأعداد المركبة 2024")
        assert "اعداد" in toks
        assert "مركبه" in toks
        assert "2024" in toks


class TestCanonicalTopics:
    """التعرّف على الموضوع المرجعي عبر صياغات متعددة."""

    @pytest.mark.parametrize(
        ("query", "expected_id"),
        [
            ("أعطني تمرين الأعداد المركبة 2024", "complex_numbers"),
            ("اعطني تمرين أعداد مركبة", "complex_numbers"),
            ("complex numbers exercise", "complex_numbers"),
            ("nombres complexes", "complex_numbers"),
            ("تمرين الاحتمالات 2024", "probability"),
            ("احتمالات", "probability"),
            ("probability", "probability"),
            ("تمرين الدوال العددية 2016", "numerical_functions"),
            ("دوال عددية", "numerical_functions"),
            ("numerical functions", "numerical_functions"),
            ("fonctions numériques", "numerical_functions"),
        ],
    )
    def test_primary_canonical_topic(self, query: str, expected_id: str) -> None:
        topic = primary_canonical_topic(query)
        assert topic is not None, f"لم يُتعرَّف على موضوع لـ {query!r}"
        assert topic.canonical_id == expected_id

    def test_no_false_positive(self) -> None:
        assert primary_canonical_topic("مرحبا كيف حالك") is None
        assert primary_canonical_topic("والد فلاح") is None

    def test_db_topic_mapping(self) -> None:
        assert CANONICAL_BY_ID["complex_numbers"].db_topic == "Complex Numbers"
        assert CANONICAL_BY_ID["probability"].db_topic == "Probability"
        assert CANONICAL_BY_ID["numerical_functions"].db_topic == "Numerical Functions"

    def test_resolve_returns_specific_first(self) -> None:
        # عند ذكر موضوع واحد، يُرجِع موضوعاً واحداً
        topics = resolve_canonical_topics("تمرين الأعداد المركبة")
        assert [t.canonical_id for t in topics] == ["complex_numbers"]
