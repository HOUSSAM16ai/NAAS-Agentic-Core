"""D-115 — البروتوكول السقراطي المنضبط (يَعكِس D-114) — جانب المونوليث.

يثبت:
1. المُطهّر المُصفّح (content_integrity._strip_garbage_markers + StreamIntegrityFilter)
   يحذف ⟦⟧ المشوّهة + تعليمات system prompt المُسرَّبة، يحفظ العربية/LaTeX.
2. قفل المفهوم (bkt_engine): متابعة حيرة بعد الاحتمالات + هلوسة مساعد «متتالية» ⇒
   يبقى المفهوم probability (مناعة ضد تسمّم السياق).
3. الـ doctrine مُعاد توجيهه (v2.0.0) + manifest متّسق + الفواصل محفوظة.
4. المثال المكشوف مُزال: لا worked_example_skill، لا worked_example_card، لا registry entry.

الكارثة (transcript حي): «اعطني الاحتمالات» → 5× «لم أفهم» → تسرّب ⟦⟧/إنجليزي/فرنسي
+ قفز إلى متتاليات/معادلات + جدران نص → انهيار الطالب.
"""

from __future__ import annotations


# ── 1. المُطهّر المُصفّح ───────────────────────────────────────────────────────
class TestBulletproofSanitizer:
    def test_strips_mangled_brackets(self) -> None:
        from app.services.skills.content_integrity_skill import _strip_garbage_markers

        for case in (
            "⟦/مثال_محلول⟧ الآن طبّق",
            "⟦مثال_محلول حدد النوع",
            "⟦/مثال_محلول⟦ نص",
            "نص ⟦مثال_محلول⟧ محتوى ⟦/مثال_محلول⟧ نهاية",
        ):
            out = _strip_garbage_markers(case)
            assert "⟦" not in out and "⟧" not in out
            assert "مثال_محلول" not in out

    def test_strips_leaked_instructions(self) -> None:
        from app.services.skills.content_integrity_skill import _strip_garbage_markers

        leak = "WARM-UP: The instruction must be rendered in a coalesced English form."
        out = _strip_garbage_markers(leak)
        assert "WARM" not in out and "instruction must" not in out

    def test_preserves_natural_arabic(self) -> None:
        from app.services.skills.content_integrity_skill import _strip_garbage_markers

        assert "مثال محلول" in _strip_garbage_markers("هذا مثال محلول بسيط")

    def test_stream_filter_strips_brackets(self) -> None:
        from app.services.skills.content_integrity_skill import StreamIntegrityFilter

        flt = StreamIntegrityFilter()
        out = flt.feed("نص ⟦مثال_محلول⟧ بعده") + flt.flush()
        assert "⟦" not in out and "⟧" not in out

    def test_sanitize_final_text_strips_garbage(self) -> None:
        from app.services.skills.content_integrity_skill import sanitize_final_text

        out = sanitize_final_text("الشرح ⟦/مثال_محلول⟦ WARM-UP: rendered in a form")
        assert "⟦" not in out and "WARM" not in out


# ── 2. قفل المفهوم (ضد تسمّم السياق) ──────────────────────────────────────────
class TestConceptLock:
    def test_confusion_followup_stays_on_student_concept(self) -> None:
        from app.services.skills.bkt_engine import classify_concept_with_context

        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            # المساعد هلوس «متتالية»/«معادلة» — يجب ألا يُسمّم التصنيف
            {"role": "assistant", "content": "حدد نوع المتتالية هندسية، معادلة 7x+8=96"},
            {"role": "user", "content": "لم اعرف كيف احل السؤال الأول"},
        ]
        assert classify_concept_with_context("لم افهم اي شيء", history) == "probability"

    def test_explicit_topic_switch_by_student_respected(self) -> None:
        from app.services.skills.bkt_engine import classify_concept_with_context

        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات"},
            {"role": "user", "content": "والآن اشرح لي المتتاليات الهندسية"},
        ]
        # أحدث مفهوم ذكره الطالب صراحةً يفوز
        assert classify_concept_with_context("لم أفهم", history) == "sequences"

    def test_direct_concept_unchanged(self) -> None:
        from app.services.skills.bkt_engine import classify_concept_with_context

        assert classify_concept_with_context("اشرح الأعداد المركبة", []) == "complex_numbers"


# ── 3. الـ doctrine المُعاد توجيهه ────────────────────────────────────────────
class TestDoctrine:
    def test_socratic_doctrine_version_bumped(self) -> None:
        from app.services.skills.doctrine import WORKED_EXAMPLE_DOCTRINE_VERSION

        assert WORKED_EXAMPLE_DOCTRINE_VERSION == "2.0.0"

    def test_manifest_consistent_and_sentinels_kept(self) -> None:
        from app.services.skills.doctrine import (
            SKILL_DOCTRINE_MANIFEST,
            WORKED_EXAMPLE_CLOSE,
            WORKED_EXAMPLE_DOCTRINE,
            WORKED_EXAMPLE_DOCTRINE_VERSION,
            WORKED_EXAMPLE_OPEN,
        )

        entry = SKILL_DOCTRINE_MANIFEST["worked_example"]
        assert entry["version"] == WORKED_EXAMPLE_DOCTRINE_VERSION
        assert entry["rules_count"] == len(WORKED_EXAMPLE_DOCTRINE)
        assert WORKED_EXAMPLE_OPEN and WORKED_EXAMPLE_CLOSE

    def test_doctrine_documents_no_reveal(self) -> None:
        from app.services.skills.doctrine import WORKED_EXAMPLE_DOCTRINE

        joined = " ".join(WORKED_EXAMPLE_DOCTRINE)
        assert "لا مثال محلول مكشوف" in joined
        assert "السلطة الوحيدة" in joined  # microservices/orchestrator authority


# ── 4. إزالة المثال المكشوف (D-114) ───────────────────────────────────────────
class TestRevealRemoved:
    def test_worked_example_skill_module_removed(self) -> None:
        import importlib.util

        assert importlib.util.find_spec("app.services.skills.worked_example_skill") is None

    def test_worked_example_card_not_whitelisted(self) -> None:
        from app.contracts.streaming import KNOWN_UI_COMPONENTS

        assert "worked_example_card" not in KNOWN_UI_COMPONENTS

    def test_registry_has_no_worked_example(self) -> None:
        from app.services.skills.registry import get_skill_registry

        assert get_skill_registry().get("worked_example") is None
