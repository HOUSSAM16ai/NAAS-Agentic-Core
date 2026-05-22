"""
اختبارات الحالة المستحيلة — D-082.

تتحقق من:
  1. تحديد الاستحالة بشكل صحيح (requested > bag_count)
  2. بنية الـ contract الكاملة (4 مراحل)
  3. وجود deep_dive للشرح الرياضي
  4. الحالة الممكنة (requested <= bag_count)
  5. المدخلات غير الصالحة (صفر أو سالب)
  6. HTTP endpoint /impossible-case
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from microservices.content_retrieval_skill.main import app
from microservices.content_retrieval_skill.src.impossible_case import (
    analyze_impossible_case,
)


@pytest.fixture
def client() -> TestClient:
    """عميل اختبار لـ content-retrieval-skill."""
    return TestClient(app)


# ── اختبارات المنطق الأساسي ───────────────────────────────────────────────────


class TestAnalyzeImpossibleCase:
    """اختبارات دالة analyze_impossible_case مباشرةً."""

    def test_draw_exceeds_bag_is_impossible(self) -> None:
        """requested > bag_count → مستحيل."""
        result = analyze_impossible_case(bag_count=2, requested=3)
        assert result.is_impossible is True
        assert result.case_type == "draw_exceeds_bag"

    def test_draw_equals_bag_is_possible(self) -> None:
        """requested == bag_count → ممكن (C(n,n)=1)."""
        result = analyze_impossible_case(bag_count=3, requested=3)
        assert result.is_impossible is False
        assert result.case_type == "none"

    def test_draw_less_than_bag_is_possible(self) -> None:
        """requested < bag_count → ممكن."""
        result = analyze_impossible_case(bag_count=5, requested=2)
        assert result.is_impossible is False

    def test_zero_bag_count_is_impossible(self) -> None:
        """bag_count=0 → مستحيل."""
        result = analyze_impossible_case(bag_count=0, requested=1)
        assert result.is_impossible is True

    def test_zero_requested_is_impossible(self) -> None:
        """requested=0 → مستحيل (لا معنى لسحب صفر)."""
        result = analyze_impossible_case(bag_count=5, requested=0)
        assert result.is_impossible is True

    def test_stage_1_contains_correct_counts(self) -> None:
        """المرحلة 1 تحتوي على الأعداد الصحيحة."""
        result = analyze_impossible_case(bag_count=2, requested=5)
        assert result.stage_1 is not None
        assert result.stage_1.bag_count == 2
        assert result.stage_1.requested == 5

    def test_stage_2_question_is_intuitive(self) -> None:
        """المرحلة 2 تحتوي على سؤال حدسي بسيط."""
        result = analyze_impossible_case(bag_count=2, requested=3)
        assert result.stage_2 is not None
        assert "2" in result.stage_2.question
        assert "3" in result.stage_2.question
        # لا معادلات في المرحلة 2
        assert "C(" not in result.stage_2.question
        assert "=" not in result.stage_2.question

    def test_stage_3_animation_is_shake(self) -> None:
        """المرحلة 3 تستخدم حركة shake للحالة المستحيلة."""
        result = analyze_impossible_case(bag_count=2, requested=3)
        assert result.stage_3 is not None
        assert result.stage_3.animation == "shake"
        assert result.stage_3.duration_ms > 0

    def test_stage_4_message_is_gentle(self) -> None:
        """المرحلة 4 تحتوي على رسالة لطيفة وواضحة."""
        result = analyze_impossible_case(bag_count=2, requested=3)
        assert result.stage_4 is not None
        assert result.stage_4.tone == "gentle"
        assert len(result.stage_4.message) > 10
        # الرسالة تذكر الأعداد
        assert "2" in result.stage_4.message
        assert "3" in result.stage_4.message

    def test_deep_dive_contains_formula(self) -> None:
        """deep_dive يحتوي على المعادلة الرياضية."""
        result = analyze_impossible_case(bag_count=2, requested=3)
        assert result.deep_dive is not None
        assert "C(" in result.deep_dive.formula
        assert len(result.deep_dive.explanation) > 20

    def test_possible_case_has_no_stages(self) -> None:
        """الحالة الممكنة لا تحتوي على مراحل."""
        result = analyze_impossible_case(bag_count=5, requested=3)
        assert result.stage_1 is None
        assert result.stage_2 is None
        assert result.stage_3 is None
        assert result.stage_4 is None
        assert result.deep_dive is None

    def test_custom_item_name_in_message(self) -> None:
        """اسم العنصر المخصص يظهر في الرسالة."""
        result = analyze_impossible_case(bag_count=2, requested=3, item_name="قلم")
        assert result.stage_4 is not None
        assert "قلم" in result.stage_4.message or "أقلام" in result.stage_4.message

    def test_large_numbers_impossible(self) -> None:
        """أعداد كبيرة: requested >> bag_count → مستحيل."""
        result = analyze_impossible_case(bag_count=10, requested=100)
        assert result.is_impossible is True
        assert result.deep_dive is not None


# ── اختبارات HTTP endpoint ────────────────────────────────────────────────────


class TestImpossibleCaseEndpoint:
    """اختبارات HTTP endpoint /impossible-case."""

    def test_impossible_case_returns_200(self, client: TestClient) -> None:
        """الـ endpoint يُعيد 200 للحالة المستحيلة."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": 2, "requested": 3, "item_name": "كرة"},
        )
        assert response.status_code == 200

    def test_impossible_case_contract_structure(self, client: TestClient) -> None:
        """الـ contract يحتوي على جميع الحقول المطلوبة."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": 2, "requested": 3, "item_name": "كرة"},
        )
        data = response.json()
        assert data["is_impossible"] is True
        assert data["case_type"] == "draw_exceeds_bag"
        assert data["stage_1"] is not None
        assert data["stage_2"] is not None
        assert data["stage_3"] is not None
        assert data["stage_4"] is not None
        assert data["deep_dive"] is not None

    def test_possible_case_returns_false(self, client: TestClient) -> None:
        """الحالة الممكنة تُعيد is_impossible=False."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": 5, "requested": 3, "item_name": "كرة"},
        )
        data = response.json()
        assert data["is_impossible"] is False
        assert data["stage_1"] is None
        assert data["deep_dive"] is None

    def test_stage_2_no_math_formula(self, client: TestClient) -> None:
        """المرحلة 2 لا تحتوي على معادلات رياضية — مبدأ D-082."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": 2, "requested": 3, "item_name": "كرة"},
        )
        data = response.json()
        question = data["stage_2"]["question"]
        # لا معادلات في المرحلة 2
        assert "C(" not in question
        assert "!" not in question

    def test_stage_3_animation_shake(self, client: TestClient) -> None:
        """المرحلة 3 تستخدم shake animation."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": 1, "requested": 5, "item_name": "كرة"},
        )
        data = response.json()
        assert data["stage_3"]["animation"] == "shake"

    def test_stage_4_tone_gentle(self, client: TestClient) -> None:
        """المرحلة 4 تستخدم نبرة لطيفة دائماً."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": 2, "requested": 10, "item_name": "كرة"},
        )
        data = response.json()
        assert data["stage_4"]["tone"] == "gentle"

    def test_deep_dive_has_formula_and_explanation(self, client: TestClient) -> None:
        """deep_dive يحتوي على formula + explanation + why_zero."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": 3, "requested": 7, "item_name": "كرة"},
        )
        data = response.json()
        dd = data["deep_dive"]
        assert "formula" in dd
        assert "explanation" in dd
        assert "why_zero" in dd
        assert len(dd["formula"]) > 5
        assert len(dd["explanation"]) > 20

    def test_default_item_name_is_kura(self, client: TestClient) -> None:
        """اسم العنصر الافتراضي هو 'كرة'."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": 2, "requested": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_impossible"] is True

    def test_invalid_negative_values(self, client: TestClient) -> None:
        """القيم السالبة ترفضها Pydantic (ge=0)."""
        response = client.post(
            "/impossible-case",
            json={"bag_count": -1, "requested": 3, "item_name": "كرة"},
        )
        assert response.status_code == 422
