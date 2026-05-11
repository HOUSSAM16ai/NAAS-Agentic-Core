"""
اختبارات الخطوة 11 — content-retrieval-skill.

تغطي:
  - intent_classifier: 30 حالة (explanation / retrieval / unknown)
  - retrieval_engine: قراءة knowledge_base الحقيقية
  - FastAPI endpoints: /retrieve + /health + /metrics
  - Prometheus metrics: تسجيل حقيقي
  - ISS-038 regression: منع التفعيل الخاطئ

قواعد الاختبار (AGENTS.md):
  - كل endpoint: happy path + error path
  - لا DB حقيقية في unit tests
  - pytest-asyncio asyncio_mode=auto
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── إضافة مسار المشروع ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from microservices.content_retrieval_skill.src.intent_classifier import (
    IntentResult,
    classify_intent,
)
from microservices.content_retrieval_skill.src.retrieval_engine import (
    ContentItem,
    RetrievalQuery,
    RetrievalResult,
    retrieve,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Intent Classifier — Unit Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestIntentClassifier:
    """اختبارات مُصنِّف النوايا — 30 حالة."""

    # ── نية الشرح (explanation) ───────────────────────────────────────────────

    def test_explanation_direct_sharh(self):
        r = classify_intent("اشرح قانون الاحتمالات")
        assert r.intent == "explanation"
        assert r.confidence >= 0.9

    def test_explanation_with_tamreen_word(self):
        """ISS-038: 'تمرين' في سياق الشرح لا يُفعِّل الاسترجاع."""
        r = classify_intent("اشرح الجزء أ من هذا التمرين")
        assert r.intent == "explanation"

    def test_explanation_help_request(self):
        r = classify_intent("ساعدني في حل هذه المسألة")
        assert r.intent == "explanation"

    def test_explanation_this_exercise(self):
        r = classify_intent("هذا التمرين صعب، وضح لي الخطوات")
        assert r.intent == "explanation"

    def test_explanation_part_a(self):
        r = classify_intent("الجزء أ من التمرين يتعلق بالاحتمالات")
        assert r.intent == "explanation"

    def test_explanation_how_question(self):
        r = classify_intent("كيف أحل مسائل الاحتمالات؟")
        assert r.intent == "explanation"

    def test_explanation_why_question(self):
        r = classify_intent("لماذا P(A∪B) = P(A) + P(B) - P(A∩B)؟")
        assert r.intent == "explanation"

    def test_explanation_what_is(self):
        r = classify_intent("ما هو الاحتمال الشرطي؟")
        assert r.intent == "explanation"

    def test_explanation_french(self):
        r = classify_intent("explain the probability theorem")
        assert r.intent == "explanation"

    def test_explanation_help_english(self):
        r = classify_intent("help me solve this exercise")
        assert r.intent == "explanation"

    def test_explanation_describe(self):
        r = classify_intent("describe the sample space")
        assert r.intent == "explanation"

    def test_explanation_part_b_english(self):
        r = classify_intent("part b of the exercise asks about probability")
        assert r.intent == "explanation"

    # ── نية الاسترجاع (retrieval) ─────────────────────────────────────────────

    def test_retrieval_bac_explicit(self):
        r = classify_intent("أريد تمرين بكالوريا في الاحتمالات")
        assert r.intent == "retrieval"
        assert r.confidence >= 0.85

    def test_retrieval_bac_keyword(self):
        r = classify_intent("تمارين بكالوريا رياضيات")
        assert r.intent == "retrieval"

    def test_retrieval_bac_french(self):
        r = classify_intent("exercice baccalauréat mathématiques")
        assert r.intent == "retrieval"

    def test_retrieval_numbered_exercise(self):
        r = classify_intent("التمرين الأول في الاحتمالات")
        assert r.intent == "retrieval"

    def test_retrieval_exercise_number_regex(self):
        r = classify_intent("تمرين 3 في الرياضيات")
        assert r.intent == "retrieval"

    def test_retrieval_exercise_with_year(self):
        r = classify_intent("تمرين احتمالات 2024")
        assert r.intent == "retrieval"

    def test_retrieval_give_me_exercise(self):
        r = classify_intent("أعطني تمرين في الاحتمالات")
        assert r.intent == "retrieval"

    def test_retrieval_fetch_exercise(self):
        r = classify_intent("جلب تمرين بكالوريا")
        assert r.intent == "retrieval"

    def test_retrieval_subject_1(self):
        r = classify_intent("الموضوع الأول في الرياضيات")
        assert r.intent == "retrieval"

    def test_retrieval_bac_english(self):
        r = classify_intent("give me a bac exercise in probability")
        assert r.intent == "retrieval"

    def test_retrieval_probability_exercise_english(self):
        r = classify_intent("probability exercise for bac")
        assert r.intent == "retrieval"

    # ── نية غير محددة (unknown) ───────────────────────────────────────────────

    def test_unknown_general_question(self):
        r = classify_intent("الاحتمالات مادة مهمة")
        assert r.intent == "unknown"

    def test_unknown_greeting(self):
        r = classify_intent("مرحبا")
        assert r.intent == "unknown"

    def test_unknown_empty_context(self):
        r = classify_intent("رياضيات")
        assert r.intent == "unknown"

    # ── خصائص IntentResult ────────────────────────────────────────────────────

    def test_result_has_reason(self):
        r = classify_intent("اشرح الاحتمالات")
        assert r.reason != ""

    def test_result_confidence_range(self):
        for q in ["اشرح", "بكالوريا", "مرحبا"]:
            r = classify_intent(q)
            assert 0.0 <= r.confidence <= 1.0

    def test_result_is_frozen(self):
        r = classify_intent("test")
        with pytest.raises((AttributeError, TypeError)):
            r.intent = "other"  # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Retrieval Engine — Unit Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRetrievalEngine:
    """اختبارات محرك الاسترجاع."""

    def test_retrieve_from_real_kb(self, tmp_path):
        """يسترجع من knowledge_base حقيقية مؤقتة."""
        md = tmp_path / "test_exercise.md"
        md.write_text(
            "---\ntitle: تمرين احتمالات 2024\nsubject: Mathematics\nyear: 2024\ntags: bac2024, probability\n---\n\n# محتوى التمرين\n\nنص التمرين هنا.",
            encoding="utf-8",
        )
        query = RetrievalQuery(question="تمرين احتمالات 2024", intent="retrieval")
        result = retrieve(query, tmp_path)
        assert result.total >= 1
        assert result.items[0].year == "2024"

    def test_retrieve_empty_kb(self, tmp_path):
        """يُعيد قائمة فارغة عند غياب الملفات."""
        query = RetrievalQuery(question="تمرين", intent="retrieval")
        result = retrieve(query, tmp_path)
        assert result.total == 0
        assert result.items == []

    def test_retrieve_skips_readme(self, tmp_path):
        """يتجاهل README.md."""
        (tmp_path / "README.md").write_text("# README", encoding="utf-8")
        query = RetrievalQuery(question="تمرين", intent="retrieval")
        result = retrieve(query, tmp_path)
        assert result.total == 0

    def test_retrieve_nonexistent_kb(self):
        """يُعيد قائمة فارغة عند غياب المجلد."""
        query = RetrievalQuery(question="تمرين", intent="retrieval")
        result = retrieve(query, Path("/nonexistent/path"))
        assert result.total == 0

    def test_retrieve_has_duration(self, tmp_path):
        """يُسجِّل زمن الاسترجاع."""
        query = RetrievalQuery(question="test", intent="retrieval")
        result = retrieve(query, tmp_path)
        assert result.duration_ms >= 0.0

    def test_retrieve_real_knowledge_base(self):
        """يختبر knowledge_base الحقيقية في المشروع."""
        kb = Path(__file__).parent.parent.parent.parent / "knowledge_base"
        if not kb.exists():
            pytest.skip("knowledge_base not found")
        query = RetrievalQuery(question="تمرين بكالوريا احتمالات 2024", intent="retrieval")
        result = retrieve(query, kb)
        # يجب أن يجد ملف bac2024_math_experimental_subject1_ex1_ex2.md
        assert result.total >= 1
        assert any("2024" in item.year or "2024" in item.file_path for item in result.items)

    def test_retrieve_max_results_respected(self, tmp_path):
        """يحترم max_results."""
        for i in range(10):
            (tmp_path / f"exercise_{i}.md").write_text(
                f"---\ntitle: تمرين {i}\nsubject: Math\nyear: 2024\ntags: bac\n---\n\nمحتوى {i}",
                encoding="utf-8",
            )
        query = RetrievalQuery(question="تمرين بكالوريا", intent="retrieval", max_results=3)
        result = retrieve(query, tmp_path)
        assert result.total <= 3


# ══════════════════════════════════════════════════════════════════════════════
# 3. FastAPI Endpoints — Integration Tests
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client(tmp_path):
    """TestClient مع KB مؤقتة."""
    # إنشاء ملف محتوى تجريبي
    md = tmp_path / "bac2024_test.md"
    md.write_text(
        "---\ntitle: تمرين احتمالات بكالوريا 2024\nsubject: Mathematics\nyear: 2024\ntags: bac2024, احتمالات\n---\n\n# التمرين\n\nنص التمرين.",
        encoding="utf-8",
    )

    with patch(
        "microservices.content_retrieval_skill.main._KB_ROOT",
        tmp_path,
    ):
        from microservices.content_retrieval_skill.main import app

        with TestClient(app) as c:
            yield c


class TestRetrieveEndpoint:
    """اختبارات /retrieve endpoint."""

    def test_retrieval_intent_returns_items(self, client):
        """happy path: طلب استرجاع صريح يُعيد نتائج."""
        resp = client.post(
            "/retrieve",
            json={"question": "أريد تمرين بكالوريا احتمالات 2024"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "retrieval"
        assert data["total"] >= 1

    def test_explanation_intent_returns_empty(self, client):
        """ISS-038: طلب الشرح يُعيد قائمة فارغة."""
        resp = client.post(
            "/retrieve",
            json={"question": "اشرح الجزء أ من هذا التمرين"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "explanation"
        assert data["total"] == 0
        assert data["items"] == []

    def test_response_has_intent_confidence(self, client):
        """الاستجابة تحتوي على confidence و reason."""
        resp = client.post("/retrieve", json={"question": "بكالوريا رياضيات"})
        assert resp.status_code == 200
        data = resp.json()
        assert "intent_confidence" in data
        assert "intent_reason" in data
        assert 0.0 <= data["intent_confidence"] <= 1.0

    def test_response_has_duration(self, client):
        """الاستجابة تحتوي على duration_ms."""
        resp = client.post("/retrieve", json={"question": "تمرين"})
        assert resp.status_code == 200
        assert resp.json()["duration_ms"] >= 0.0

    def test_empty_question_rejected(self, client):
        """السؤال الفارغ يُرفض بـ 422."""
        resp = client.post("/retrieve", json={"question": ""})
        assert resp.status_code == 422

    def test_missing_question_rejected(self, client):
        """الطلب بدون question يُرفض بـ 422."""
        resp = client.post("/retrieve", json={})
        assert resp.status_code == 422

    def test_max_results_respected(self, client):
        """max_results يُحدِّد عدد النتائج."""
        resp = client.post(
            "/retrieve",
            json={"question": "تمرين بكالوريا", "max_results": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] <= 1


class TestHealthEndpoint:
    """اختبارات /health endpoint."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_fields(self, client):
        data = client.get("/health").json()
        assert data["status"] == "healthy"
        assert data["service"] == "content-retrieval-skill"
        assert data["step"] == "11"
        assert "kb_files" in data

    def test_health_kb_files_count(self, client):
        """يُعيد عدد ملفات KB الصحيح."""
        data = client.get("/health").json()
        assert data["kb_files"] >= 1  # ملف bac2024_test.md


class TestMetricsEndpoint:
    """اختبارات /metrics endpoint."""

    def test_metrics_returns_200(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_has_cogniforge_prefix(self, client):
        """المقاييس تحمل prefix cogniforge_retrieval_."""
        # استدعاء /retrieve أولاً لتوليد مقاييس
        client.post("/retrieve", json={"question": "تمرين بكالوريا"})
        resp = client.get("/metrics")
        assert "cogniforge_retrieval" in resp.text

    def test_metrics_records_requests(self, client):
        """cogniforge_retrieval_requests_total يزداد بعد كل طلب."""
        client.post("/retrieve", json={"question": "تمرين بكالوريا"})
        client.post("/retrieve", json={"question": "اشرح الاحتمالات"})
        resp = client.get("/metrics")
        assert "cogniforge_retrieval_requests_total" in resp.text

    def test_metrics_startup_info(self, client):
        """cogniforge_retrieval_startup_info موجود."""
        resp = client.get("/metrics")
        assert "cogniforge_retrieval_startup_info" in resp.text


# ══════════════════════════════════════════════════════════════════════════════
# 4. ISS-038 Regression Tests — منع التفعيل الخاطئ
# ══════════════════════════════════════════════════════════════════════════════


class TestISS038Regression:
    """
    اختبارات انحدار ISS-038.

    قبل الإصلاح: أي سؤال يحتوي "تمرين" أو "احتمالات" كان يُطلق
    استرجاع تمرين الاحتمالات بشكل ثابت بغض النظر عن السياق.
    """

    @pytest.mark.parametrize(
        "question",
        [
            "اشرح الجزء أ من هذا التمرين",
            "ساعدني في حل تمرين الاحتمالات",
            "كيف أحل مسائل الاحتمالات؟",
            "هذا التمرين صعب، وضح لي",
            "ما هو مفهوم الاحتمال الشرطي؟",
            "لماذا نستخدم قانون الاحتمالات؟",
            "help me with this probability exercise",
            "explain part a of the exercise",
        ],
    )
    def test_explanation_context_blocks_retrieval(self, question):
        """سياق الشرح يمنع الاسترجاع حتى مع وجود 'تمرين' أو 'احتمالات'."""
        r = classify_intent(question)
        assert r.intent == "explanation", (
            f"Expected 'explanation' for '{question}', got '{r.intent}' (reason: {r.reason})"
        )

    @pytest.mark.parametrize(
        "question",
        [
            "أريد تمرين بكالوريا في الاحتمالات",
            "تمارين بكالوريا رياضيات 2024",
            "التمرين الأول في الموضوع الأول",
            "give me a bac exercise in probability",
            "تمرين 2 في الاحتمالات",
        ],
    )
    def test_explicit_retrieval_triggers_correctly(self, question):
        """طلب الجلب الصريح يُفعِّل الاسترجاع بشكل صحيح."""
        r = classify_intent(question)
        assert r.intent == "retrieval", (
            f"Expected 'retrieval' for '{question}', got '{r.intent}' (reason: {r.reason})"
        )
