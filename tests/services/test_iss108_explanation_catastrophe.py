"""
ISS-108 (D-097) — Catastrophic Explanation Fixes — regression tests.

تغطي الكوارث الأربع المؤكَّدة حياً على بيانات الإنتاج (conv 731):
  1. هلوسة تسرّب الموضوع عند «أكمل الشرح» (لا سياق التمرين) → علامات المتابعة.
  2. تقطيع نثر LLM إلى «خطوات» وهمية → تعطيل `_try_build_math_ui_component`.
  3. الكيس الناقص (أبيض فقط) بسبب Markdown/LaTeX ملتصق بالأعداد → إصلاح التقطيع.
  4. حارس الـ doctrine ضد التسرّب + جدار النص (الإصدار 2.2.0).
"""

from __future__ import annotations


# ── Fix 3: استخراج التركيبة من نص مُنسَّق (Markdown + LaTeX) ──────────────────
class TestUrnCompletenessLatexMarkdown:
    """الكيس يجب أن يلتقط الألوان الثلاثة رغم `**` و `\\(...\\)` الملتصقة بالأعداد."""

    def _real_exercise_text(self) -> str:
        # نص الإنتاج الفعلي (msg 3408) — Markdown bold + LaTeX inline.
        return (
            "يحتوي كيس على **11 كرة متماثلة** موزعة كما يلي:\n"
            "- **كرتان بيضاوان** مرقمتان بـ: \\(1\\)، \\(3\\)\n"
            "- **أربع كرات حمراء** مرقمة بـ: \\(0\\)، \\(1\\)، \\(1\\)، \\(3\\)\n"
            "- **خمس كرات خضراء** مرقمة بـ: \\(0\\)، \\(1\\)، \\(1\\)، \\(3\\)، \\(4\\)"
        )

    def test_extracts_all_three_colors(self) -> None:
        from app.services.skills.probability_skill import ProbabilityCalculatorSkill

        ents = ProbabilityCalculatorSkill._extract_count_entities(self._real_exercise_text())
        labels = {label: count for label, _neg, count in ents}
        assert labels.get("كرة حمراء") == 4, labels
        assert labels.get("كرة بيضاء") == 2, labels
        assert labels.get("كرة خضراء") == 5, labels

    def test_full_story_urn_has_all_colors(self) -> None:
        """البطاقة البصرية الشاملة يجب ألا تعرض الأبيض وحده (كارثة الإنتاج)."""
        from app.services.skills.probability_skill import (
            FullExerciseStoryOutput,
            ProbabilityCalculatorSkill,
            ProbabilityInput,
        )

        skill = ProbabilityCalculatorSkill()
        history = [{"role": "assistant", "content": self._real_exercise_text()}]
        out = skill.analyze(
            ProbabilityInput(
                question="لم أفهم، اشرح لي كل شيء عن سحب 3 كرات دفعة واحدة",
                history=history,
            )
        )
        if isinstance(out, FullExerciseStoryOutput):
            # ابحث عن أي مرحلة تحمل urn/groups وتأكد من وجود الألوان الثلاثة.
            import json as _j

            blob = _j.dumps([s.numerical_state for s in out.exercise_steps], ensure_ascii=False)
            assert "حمراء" in blob and "خضراء" in blob, blob[:300]


# ── Fix 1: علامات المتابعة «أكمل الشرح» تربط بتمرين السياق ────────────────────
class TestContinuationMarkersBindContext:
    def test_continue_markers_recognized(self) -> None:
        from app.services.capabilities.exercise_retrieval import (
            _is_followup_explanation_request,
        )

        for q in ["أكمل الشرح", "اكمل", "كمل الشرح", "تابع", "واصل", "continue", "go on"]:
            assert _is_followup_explanation_request(q.lower()) is True, q

    def test_continue_binds_to_history_exercise(self) -> None:
        """«أكمل الشرح» يجب أن يُربَط بتمرين بكالوريا مذكور في السياق."""
        from app.services.capabilities.exercise_retrieval import (
            ExerciseRetrievalRequest,
            detect_explanation_with_context,
        )

        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {
                "role": "assistant",
                "content": "## التمرين الأول — الاحتمالات (بكالوريا 2024) ... كيس فيه 11 كرة",
            },
        ]
        decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question="أكمل الشرح"),
            history_messages=history,
        )
        # يجب أن يُعرَف ويُربَط بتمرين (لا يسقط للمسار العام → هلوسة).
        assert decision.recognized is True
        assert decision.matched_entry is not None


# ── Fix 2: لا تقطيع لنثر LLM إلى بطاقة خطوات وهمية ────────────────────────────
class TestNoProseChopping:
    def test_try_build_math_ui_component_disabled(self) -> None:
        from app.api.routers.customer_chat import _try_build_math_ui_component

        prose = (
            "## احتمال شرطي\n\nبالعربي: نقسم الحالات.\n"
            "1. بالعربي\n2. أتمنى أن تكون الفكرة واضحة\n" * 20
        )
        assert _try_build_math_ui_component(prose) is None
        assert _try_build_math_ui_component("") is None


# ── Fix 4: doctrine الشرح — حارس التسرّب + جدار النص ──────────────────────────
class TestExplanationDoctrineGuard:
    def test_version_bumped(self) -> None:
        from app.services.skills.doctrine import EXPLANATION_DOCTRINE_VERSION

        # ISS-108 رفعها إلى 2.2.0؛ D-106 (ISS-114) رفعها إلى 2.3.0 (قاعدة لا-HTML).
        # نتحقق ≥ 2.2.0 (رتيب) فلا يكسر الاختبار أي رفع لاحق.
        parts = tuple(int(p) for p in EXPLANATION_DOCTRINE_VERSION.split("."))
        assert parts >= (2, 2, 0)

    def test_prompt_has_anti_leak_and_within_budget(self) -> None:
        from app.services.skills.doctrine import EXERCISE_EXPLANATION_SYSTEM_PROMPT

        prompt = EXERCISE_EXPLANATION_SYSTEM_PROMPT
        assert len(prompt) <= 1000, len(prompt)
        # حارس التسرّب الموضوعي
        assert "خارجي" in prompt
        # المراسي الإلزامية (CI gate)
        for anchor in ("الإجابة النموذجية", "LaTeX", "حرفياً"):
            assert anchor in prompt, anchor

    def test_doctrine_contains_anti_leak_rule(self) -> None:
        from app.services.skills.doctrine import EXPLANATION_DOCTRINE

        joined = " ".join(EXPLANATION_DOCTRINE)
        assert "موضوع خارجي" in joined
        assert "جدار النص" in joined or "جداول" in joined
