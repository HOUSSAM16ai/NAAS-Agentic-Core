"""ISS-112 — اختبارات «أعطني السؤال رقم N فقط» (question-only retrieval).

الفضيحة المُشخَّصة حياً (2026-06-11): طلب «السؤال رقم 2 فقط» كان يُرجع
التمرين كاملاً أو حلاً مُهلوَساً بنص مشوه. الحل الحتمي: كاشف نية + مُقتطِع
من النص الرسمي — صفر LLM. + إصلاح تصنيف BKT («الأعداد المركبة» ⇒
complex_numbers لا general — درس ISS-109 المتكرر).
"""

from __future__ import annotations

from pathlib import Path

from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    _extract_numbered_question,
    detect_question_only_request,
)
from app.services.skills.bkt_engine import classify_concept

REPO_ROOT = Path(__file__).resolve().parents[2]

_COMPLEX_HISTORY = [
    {"role": "user", "content": "اعطني تمرين الأعداد المركبة لسنة 2024"},
    {
        "role": "assistant",
        "content": "## التمرين الثاني (04 نقاط) — الأعداد المركبة بكالوريا 2024 الموضوع الأول ...",
    },
]


class TestScandalTranscripts:
    """عبارات الفضيحة الحرفية من بلاغ المستخدم — يجب أن تُقتطع حتمياً."""

    def test_question_2_complex_with_only_marker(self):
        d = detect_question_only_request(
            ExerciseRetrievalRequest(
                question="اعطني سؤال رقم 2 الخاص بالاعداد المركبة فقط السؤال فقط"
            ),
            history_messages=_COMPLEX_HISTORY,
        )
        assert d.recognized and d.question_number == 2
        assert d.reason == "question_only_sliced"
        assert "جد لاحقة النقطة" in d.sliced_content
        # السؤالان الآخران لا يتسربان
        assert "الشكل المثلثي" not in d.sliced_content
        assert "حل في مجموعة الأعداد المركبة" not in d.sliced_content

    def test_bare_question_2_followup(self):
        d = detect_question_only_request(
            ExerciseRetrievalRequest(question="اعطني السؤال رقم 2"),
            history_messages=_COMPLEX_HISTORY,
        )
        assert d.recognized and d.question_number == 2
        assert "جد لاحقة النقطة" in d.sliced_content

    def test_without_solution_phrasing(self):
        d = detect_question_only_request(
            ExerciseRetrievalRequest(question="اريد نص السؤال رقم 2 بدون حل السؤال فقط باختصار"),
            history_messages=_COMPLEX_HISTORY,
        )
        assert d.recognized and d.question_number == 2

    def test_followup_without_number_resolves_from_history(self):
        history = [
            *_COMPLEX_HISTORY,
            {"role": "user", "content": "اعطني السؤال رقم 2"},
            {"role": "assistant", "content": "..."},
        ]
        d = detect_question_only_request(
            ExerciseRetrievalRequest(question="اريد السؤال فقط"),
            history_messages=history,
        )
        assert d.recognized and d.question_number == 2

    def test_probability_question_2_returns_all_part_matches(self):
        """البند 2 موجود في جزأين — الصدق: نُرجِع كليهما مع عنوان جزئه."""
        d = detect_question_only_request(
            ExerciseRetrievalRequest(question="اعطني السؤال رقم 2 من تمرين الاحتمالات بدون حل"),
            history_messages=None,
        )
        assert d.recognized and d.question_number == 2
        assert "الاحتمال الشرطي" in d.sliced_content  # (1) بند 2
        assert "P(X > 1)" in d.sliced_content or "X > 1" in d.sliced_content  # (2) بند 2
        # نص المعطيات الكامل (الكيس/الكرات) لا يُغرق الطالب
        assert "كرتان بيضاوان" not in d.sliced_content


class TestNonHijacking:
    """الكاشف لا يختطف الشرح ولا الاسترجاع الكامل العادي."""

    def test_explanation_request_not_hijacked(self):
        d = detect_question_only_request(
            ExerciseRetrievalRequest(question="اشرح السؤال رقم 2"),
            history_messages=_COMPLEX_HISTORY,
        )
        assert not d.recognized
        assert d.reason == "explanation_intent_wins"

    def test_full_exercise_request_not_hijacked(self):
        d = detect_question_only_request(
            ExerciseRetrievalRequest(question="اعطني تمرين الدوال العددية لسنة 2016"),
            history_messages=None,
        )
        assert not d.recognized

    def test_general_question_not_hijacked(self):
        d = detect_question_only_request(
            ExerciseRetrievalRequest(question="ما هو قانون نيوتن الثاني؟"),
            history_messages=None,
        )
        assert not d.recognized

    def test_no_exercise_context_fails_open(self):
        d = detect_question_only_request(
            ExerciseRetrievalRequest(question="اعطني السؤال رقم 2"),
            history_messages=None,
        )
        assert not d.recognized
        assert d.reason == "no_exercise_context"


class TestSlicer:
    def test_extracts_numbered_item_with_part_header(self):
        display = (
            "## التمرين الثاني — الأعداد المركبة\n\n"
            "**(II)** في المستوي المركب:\n\n"
            "1. اكتب على الشكل المثلثي.\n"
            "2. جد لاحقة النقطة D.\n"
            "3. بيّن أن الرباعي معين.\n"
        )
        sliced = _extract_numbered_question(display, 2)
        assert sliced is not None
        assert "جد لاحقة النقطة D" in sliced
        assert "**(II)**" in sliced  # عنوان الجزء للسياق
        assert "الشكل المثلثي" not in sliced
        assert "الرباعي معين" not in sliced

    def test_arabic_indic_digits_supported(self):
        display = "**(I)**\n\n١. البند الأول.\n٢. البند الثاني.\n"
        sliced = _extract_numbered_question(display, 2)
        assert sliced is not None and "البند الثاني" in sliced

    def test_missing_number_returns_none(self):
        assert _extract_numbered_question("1. وحيد\n", 7) is None


class TestBKTConceptFix:
    """«تتبّع المعرفة: general» لسؤال أعداد مركبة — درس ISS-109 المتكرر."""

    def test_definite_plural_forms_classify_complex(self):
        for q in (
            "اعطني سؤال رقم 2 الخاص بالاعداد المركبة",
            "تمرين الأعداد المركبة",
            "حل المعادلة في مجموعة الاعداد المركبة",
            "العدد المركب z",
        ):
            assert classify_concept(q) == "complex_numbers", q

    def test_general_still_general(self):
        assert classify_concept("ما هي عاصمة الجزائر؟") == "general"


class TestRoutingOrder:
    """الـ preempt الجديد في موضعه الصحيح: بعد التحية وقبل المفهرَس."""

    CLIENT_SRC = (REPO_ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
        encoding="utf-8"
    )

    def test_question_only_between_greeting_and_indexed(self):
        greeting_pos = self.CLIENT_SRC.index("_greeting_fastpath_response")
        qo_pos = self.CLIENT_SRC.index("_stream_question_only_response(question, history_messages)")
        indexed_pos = self.CLIENT_SRC.index("if self._has_indexed_match(")
        assert greeting_pos < qo_pos < indexed_pos

    def test_zero_chunks_falls_through(self):
        """صفر قطع مبثوثة ⇒ المسار يتابع (الإنهاء مشروط بالبثّ)."""
        qo_pos = self.CLIENT_SRC.index("qo_streamed_chars = 0")
        seg = self.CLIENT_SRC[qo_pos : qo_pos + 1600]
        assert "if qo_streamed_chars > 0:" in seg
