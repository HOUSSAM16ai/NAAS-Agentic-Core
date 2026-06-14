"""ISS-115 / D-113 — وَهْم الإتقان: Socratic No-Answer regression suite.

يثبت أن النظام:
1. يحجب كل نتيجة نهائية صريحة (P(A)=14/165، C(11,3)=165، E(X)=1.73، $$\\boxed{}$$).
2. لا يلمس الصيغ التعليمية الوسيطة (نستخدم C(n,k)، صيغة رمزية) — صفر false-positive.
3. الـ doctrine السقراطي يمنع كشف الحل صراحةً (EXPLANATION_DOCTRINE v3.x).
4. الحارس موصول في sanitize_final_text + local_graph (no-ZOMBIE) + registry.

الكارثة (transcript حي): «اشرح السؤال الأول من تمرين الاحتمالات» كان يُخرج الحل
الكامل بكل النتائج → وهم الطلاقة → انهيار يوم الامتحان.
"""

from __future__ import annotations

import pytest


# ── 1. الحارس الحتمي: حجب النتائج النهائية ───────────────────────────────────
class TestRedactFinalAnswers:
    def test_redacts_probability_results(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        text = "العدد الكلي = C(11,3) = 165 إذن P(A)=14/165 ثم P(B)=56/165"
        out, n = redact_final_answers(text)
        assert n >= 3
        for leak in ("165", "14/165", "56/165"):
            assert leak not in out, f"leaked: {leak} in {out!r}"

    def test_redacts_expectation(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        out, n = redact_final_answers("إذن الأمل الرياضي E(X)=1.73")
        assert n >= 1
        assert "1.73" not in out

    def test_redacts_boxed_keeps_latex_valid(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        out, n = redact_final_answers(r"النتيجة في $$\boxed{14/165}$$")
        assert n >= 1
        assert "14/165" not in out
        assert "\\boxed{?}" in out  # الصندوق يبقى — فارغاً يدعو للحساب

    def test_redacts_distribution_table(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        out, n = redact_final_answers("P(X=0)=10/165 و P(X=1)=45/165 و P(X=2)=70/165")
        assert n >= 3
        for leak in ("10/165", "45/165", "70/165"):
            assert leak not in out

    def test_redacts_final_answer_marker_line(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        out, n = redact_final_answers("الإجابة النهائية: P(A) يساوي 14/165 بالضبط")
        assert n >= 1
        assert "14/165" not in out

    # ── صفر false-positive: الصيغ التعليمية تبقى ──────────────────────────────
    def test_preserves_intermediate_teaching(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        text = "نستخدم C(n,k) لأن الترتيب لا يهم في السحب الآني"
        out, n = redact_final_answers(text)
        assert n == 0
        assert out == text

    def test_preserves_symbolic_formula(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        text = r"التوافيق: $C(n,k) = \frac{n!}{k!(n-k)!}$ هي عدد الطرق"
        out, n = redact_final_answers(text)
        assert n == 0, f"false-positive redaction: {out!r}"

    def test_empty_and_blank_safe(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        assert redact_final_answers("") == ("", 0)
        assert redact_final_answers("   ")[1] == 0

    def test_idempotent(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        once, _ = redact_final_answers("P(A)=14/165 و $$\\boxed{165}$$")
        twice, n2 = redact_final_answers(once)
        assert n2 == 0
        assert twice == once


class TestRedactChunk:
    def test_chunk_strips_boxed_only(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_chunk

        assert "165" not in redact_chunk(r"الجواب $$\boxed{165}$$ هنا")

    def test_chunk_passthrough_without_boxed(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_chunk

        s = "ما هي أول خطوة في عدّ الحالات؟"
        assert redact_chunk(s) == s


class TestAnswerRedactionSkill:
    def test_skill_contract(self) -> None:
        from app.services.skills.answer_redaction_skill import (
            AnswerRedactionOutput,
            get_answer_redaction_skill,
        )

        out = get_answer_redaction_skill().redact("P(A)=14/165")
        assert isinstance(out, AnswerRedactionOutput)
        assert out.applied and out.redactions >= 1
        assert "14/165" not in out.redacted_text

    def test_skill_noop_on_clean_text(self) -> None:
        from app.services.skills.answer_redaction_skill import get_answer_redaction_skill

        out = get_answer_redaction_skill().redact("ما رأيك أن نبدأ بعدّ الحالات الكلية؟")
        assert not out.applied


# ── 2. الـ doctrine السقراطي ─────────────────────────────────────────────────
class TestSocraticDoctrine:
    def test_version_bumped_to_3(self) -> None:
        from app.services.skills.doctrine import EXPLANATION_DOCTRINE_VERSION

        assert int(EXPLANATION_DOCTRINE_VERSION.split(".")[0]) >= 3

    def test_doctrine_forbids_revealing_answer(self) -> None:
        from app.services.skills.doctrine import EXPLANATION_DOCTRINE

        joined = " ".join(EXPLANATION_DOCTRINE)
        assert "لا تكشف" in joined
        assert "ممنوع" in joined

    def test_old_leak_rule_removed(self) -> None:
        """قاعدة «النتيجة النهائية في $$\\boxed{}$$» الكارثية يجب أن تكون أُزيلت."""
        from app.services.skills.doctrine import EXPLANATION_DOCTRINE

        joined = " ".join(EXPLANATION_DOCTRINE)
        assert "النتيجة النهائية في" not in joined

    def test_prompt_socratic(self) -> None:
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        assert len(prompt) <= 1000
        assert "سقراطية" in prompt
        assert "ممنوع" in prompt and "نتيجة نهائية" in prompt
        for anchor in ("الإجابة النموذجية", "LaTeX", "حرفياً"):
            assert anchor in prompt

    def test_manifest_answer_redaction_consistent(self) -> None:
        from app.services.skills.doctrine import (
            ANSWER_REDACTION_DOCTRINE,
            ANSWER_REDACTION_DOCTRINE_VERSION,
            SKILL_DOCTRINE_MANIFEST,
        )

        entry = SKILL_DOCTRINE_MANIFEST["answer_redaction"]
        assert entry["version"] == ANSWER_REDACTION_DOCTRINE_VERSION
        assert entry["rules_count"] == len(ANSWER_REDACTION_DOCTRINE)
        assert entry["consumed_by"]  # no-ZOMBIE


# ── 3. التوصيل (no-ZOMBIE) ───────────────────────────────────────────────────
class TestWiring:
    def test_sanitize_final_text_redacts(self) -> None:
        """D-113: sanitize_final_text (orchestrator + local) يحجب النتيجة."""
        from app.services.skills.content_integrity_skill import sanitize_final_text

        out = sanitize_final_text("الخلاصة: P(A)=14/165")
        assert "14/165" not in out

    def test_registry_has_answer_redaction(self) -> None:
        from app.services.skills.registry import get_skill_registry

        desc = get_skill_registry().get("answer_redaction")
        assert desc is not None
        assert desc.consumed_by  # no-ZOMBIE

    def test_exported_at_package_level(self) -> None:
        from app.services.skills import (
            AnswerRedactionSkill,
            get_answer_redaction_skill,
            redact_final_answers,
        )

        assert AnswerRedactionSkill and get_answer_redaction_skill and redact_final_answers


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
