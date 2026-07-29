from __future__ import annotations

"""
ISS-138 (D-185) — «النظام لا يستطيع تعريف ما يطبعه»: طبقة الرموز الرياضية.

الكارثة الحيّة (transcript BAC-2024، post-D-184): الطالب سأل **«ماذا نقصد بحرف C»** —
أي عن رمزٍ **طبعه المعلّم نفسه** على الشاشة — فتُجوهِل سؤاله تماماً، وأُعيدت عليه كتلة
الاشتقاق نفسها (`C(4,3)=4` · `C(5,3)=10` · المجموع 14) **مضافاً إليها** `C(11,3)=165`.
أي أنّ النظام ردّ على «لم أفهم الرمز» بإعادة ما لم يُفهَم + تسريب نتائج جديدة.

الجذور الأربعة:
1. `PROPERTY_REGISTRY["combinations"]` يملك الجواب المثالي منذ D-162، لكن `markers`
   مفتاحها **اسم المفهوم** («التوافيق») لا **الرمز** ⇒ من لا يعرف الاسم لا يصل للتعريف.
2. `_is_short_answer_in_dialogue` يعدّ **أي** رسالة ≤8 كلمات «إجابة تُقيَّم» بلا فحص صيغة
   السؤال ⇒ «ماذا نقصد بحرف C؟» (4 كلمات) تُوجَّه لمحرّك التصعيد بدل أن تُجاب.
3. قوائم العلامات لا تتّفق: `_detect_conceptual_question` تحوي «معنى» لا «نقصد».
   و`_build_cognitive_response` بلا فرع `combinations` إطلاقاً (قيمة enum ميتة).
4. حارس التكرار يقسم على `len(cand_tokens)` ⇒ «تكرار + إضافة» (مجموعة فائقة) يهرب
   من العتبة ⇒ الحارس أعمى عن الشكل الحرفي للكارثة.

الإصلاح (D-185): سجلّ رموز قانوني (`shared/notation/registry.py`) + خدمة مصغّرة
API-first (`notation-service :8011`) + مهارة `NotationSkill` بتدهور رشيق + توصيل واحد
يُكمِل `interpret()` ولا يُظلّله + بوّابة الفعل الكلامي + توحيد العلامات + نسبة تداخل
متماثلة + بوّابتا CI («لا رمز يتيم» + تكافؤ السجلّ).
"""

from types import SimpleNamespace

import pytest

from app.services.skills.notation_skill import NotationSkill, get_notation_skill
from app.services.skills.probability_brain.cognitive_verification import (
    CognitiveVerificationMixin,
)
from app.services.skills.probability_tutor_brain import ProbabilityTutorBrain
from app.services.skills.semantic_property_skill import SemanticPropertySkill
from shared.notation import NOTATION_REGISTRY, all_symbols, define, resolve

#: سؤال الكارثة الحرفي من transcript المالك.
_CATASTROPHE_Q = "ماذا نقصد بحرف C"

#: أرقام التمرين التي يجب ألّا تتسرّب عبر باب التعريف أبداً (D-113).
_LEAK_NUMBERS = ("14", "165", "56")

#: الكتلة التي بُثّت في الدور الثالث من الترانسكريبت.
_TURN3 = (
    "عدد الحالات الملائمة:\n"
    "كرة حمراء: $C_4^3 = 4$\n"
    "كرة بيضاء: مستحيلة (أقل من 3)\n"
    "كرة خضراء: $C_5^3 = 10$\n"
    "نجمعها: 4 + 10 = 14"
)

#: ما رشّحه الدور الرابع — **مجموعة فائقة** من الدور الثالث (شكل الكارثة الحرفي).
_TURN4_SUPERSET = (
    "## الحل الكامل خطوة بخطوة\n"
    "كل الطرق الممكنة لسحب 3 كرات من 11: $C_{11}^{3} = 165$\n"
    "عدد الحالات الملائمة:\n"
    "كرة حمراء: $C_4^3 = 4$\n"
    "كرة بيضاء: مستحيلة (أقل من 3)\n"
    "كرة خضراء: $C_5^3 = 10$\n"
    "نجمعها: 4 + 10 = 14\n"
    "والآن ركّب الاحتمال بنفسك."
)


def _dialogue_history() -> list[dict[str, str]]:
    """تاريخ الحوار كما كان لحظة سؤال الطالب عن الرمز."""
    return [
        {"role": "user", "content": "كيف افهم هذا التمرين؟"},
        {"role": "assistant", "content": "أيّ الألوان يمكن أن تعطينا 3 كرات من نفس اللون؟"},
        {"role": "user", "content": "لونين فقط الأبيض لا يمكن"},
        {"role": "assistant", "content": _TURN3},
    ]


class TestCatastropheTranscriptReplay:
    """الجذر ١ — سؤال الترانسكريبت الحرفي يُجاب بتعريف، لا بإعادة اشتقاق."""

    def test_letter_c_question_is_answered(self) -> None:
        out = SemanticPropertySkill().interpret(_CATASTROPHE_Q)
        assert out is not None, "سؤال «ماذا نقصد بحرف C» يجب أن يُجاب — لا أن يسقط"
        assert out.property_id == "combinations"
        assert out.source == "deterministic", "الحقيقة الرمزية قبل اللغة — لا LLM هنا"

    def test_answer_defines_the_symbol(self) -> None:
        out = SemanticPropertySkill().interpret(_CATASTROPHE_Q)
        assert out is not None
        shown = f"{out.title}\n{out.definition}"  # ما يراه الطالب فعلاً
        assert "التوافيق" in shown, "الطالب يجب أن يعرف **اسم** ما يرمز إليه C"
        assert "الترتيب" in shown, "جوهر التوافيق: الاختيار دون ترتيب"

    def test_answer_leaks_no_exercise_numbers(self) -> None:
        """التعريف ليس إجابة (D-113): ممنوع تسريب 14 أو 165 عبر هذا الباب."""
        out = SemanticPropertySkill().interpret(_CATASTROPHE_Q)
        assert out is not None
        for number in _LEAK_NUMBERS:
            assert number not in out.definition, f"تسريب الرقم {number} في تعريف الرمز"

    @pytest.mark.parametrize(
        "question",
        [
            "ماذا نقصد بحرف C",
            "ما معنى حرف C",
            "ما معنى الرمز C",
            "واش يعني حرف C",
            "شنو يقصد بحرف c",
            "ماذا يعني الرمز c في هذا التمرين",
        ],
    )
    def test_phrasing_variants_all_resolve(self, question: str) -> None:
        """الطالب لا يكتب صيغة واحدة — كل صيغ السؤال عن الرمز تصل للتعريف."""
        entry = resolve(question)
        assert entry is not None, f"صيغة غير مُغطّاة: {question!r}"
        assert entry.symbol == "C(n,k)"


class TestEventLetterDisambiguation:
    """التباس «الحرف C» بـ«الحادثة C» كارثي — الحوادث في التمرين تُسمّى A/B/C/D."""

    @pytest.mark.parametrize(
        "question",
        [
            "ما هي الحادثة C",
            "ماذا نقصد بالحادثة C",
            "الحدث C جداء أرقامها زوجي",
        ],
    )
    def test_event_questions_are_not_notation(self, question: str) -> None:
        assert resolve(question) is None, "سؤال عن حادثة التمرين ليس سؤالاً عن الرمز"

    def test_event_path_still_answered_by_existing_registry(self) -> None:
        """لا انحدار: مسار الحوادث القائم يبقى هو المُجيب لأسئلة الحوادث."""
        out = SemanticPropertySkill().interpret("ما هي الحادثة C")
        assert out is not None and out.property_id == "product_even"

    def test_compute_requests_are_not_hijacked(self) -> None:
        """طلب الحساب يبقى للمحرك الرمزي — التعريف لا يخطف دوراً حسابياً."""
        assert resolve("احسب احتمال الحادثة A") is None
        assert resolve("بين ان P(B)=56/165") is None


class TestShortQuestionIsNotAnAnswer:
    """الجذر ٢ — «ماذا نقصد بحرف C؟» أربع كلمات، وليست إجابة قصيرة تُقيَّم."""

    def test_definitional_question_is_not_a_short_answer(self) -> None:
        assert (
            ProbabilityTutorBrain._is_short_answer_in_dialogue(
                "ماذا نقصد بحرف C؟", _dialogue_history()
            )
            is False
        )

    def test_real_short_answer_still_evaluated(self) -> None:
        assert (
            ProbabilityTutorBrain._is_short_answer_in_dialogue(
                "لونين فقط الأبيض لا يمكن", _dialogue_history()
            )
            is True
        )

    def test_hal_confirmation_remains_an_answer(self) -> None:
        """عدم انحدار D-155: «هل هي 14 من 165» إجابة تطلب تأكيداً لا سؤالاً."""
        assert (
            ProbabilityTutorBrain._is_short_answer_in_dialogue(
                "هل هي 14 من 165", _dialogue_history()
            )
            is True
        )


class TestConceptualMarkerUnification:
    """الجذر ٣ — «نقصد» كانت مفقودة بينما «معنى»/«المقصود» حاضرتان."""

    def test_naqsud_is_conceptual(self) -> None:
        assert ProbabilityTutorBrain._detect_conceptual_question("ماذا نقصد بحرف C") is True

    def test_existing_conceptual_markers_unchanged(self) -> None:
        assert ProbabilityTutorBrain._detect_conceptual_question("ما معنى التوافيق") is True
        assert ProbabilityTutorBrain._detect_conceptual_question("ما الفرق بينهما") is True


class TestSupersetRepeatGuard:
    """الجذر ٤ — «تكرار + إضافة» كان يهرب من عتبة الحارس."""

    def test_superset_repeat_is_caught(self) -> None:
        history = [{"role": "assistant", "content": _TURN3}]
        assert CognitiveVerificationMixin._recently_emitted(_TURN4_SUPERSET, history) is True

    def test_near_dup_is_symmetric(self) -> None:
        assert CognitiveVerificationMixin._near_dup(_TURN4_SUPERSET, _TURN3) is True
        assert CognitiveVerificationMixin._near_dup(_TURN3, _TURN4_SUPERSET) is True

    def test_unrelated_text_not_flagged(self) -> None:
        history = [{"role": "assistant", "content": _TURN3}]
        assert (
            CognitiveVerificationMixin._recently_emitted(
                "لنتحدّث الآن عن الاحتمال الشرطي وقانونه", history
            )
            is False
        )

    def test_overlap_ratio_divides_by_the_smaller_side(self) -> None:
        ratio = CognitiveVerificationMixin._overlap_ratio({"a", "b"}, {"a", "b", "c", "d", "e"})
        assert ratio == 1.0, "المجموعة الفائقة تكرارٌ كامل للأصغر"
        assert CognitiveVerificationMixin._overlap_ratio(set(), {"a"}) == 0.0


class TestNotationRegistryContract:
    """سلامة السجلّ نفسه — كل رمز قابل للتعريف وأمثلته محايدة."""

    def test_every_symbol_is_definable(self) -> None:
        for symbol in all_symbols():
            assert define(symbol) is not None, f"رمز غير قابل للتعريف: {symbol}"

    def test_every_entry_is_complete(self) -> None:
        for entry in NOTATION_REGISTRY:
            assert entry.title.strip()
            assert entry.definition.strip()
            assert entry.example.strip()
            assert entry.markers, f"إدخال بلا علامات لا يمكن الوصول إليه: {entry.symbol}"

    def test_examples_are_neutral(self) -> None:
        """المثال المحايد هو ما يمنع «التعريف» من أن يصير باباً خلفيّاً للحل."""
        for entry in NOTATION_REGISTRY:
            for number in _LEAK_NUMBERS:
                assert number not in entry.example, f"{entry.symbol} يسرّب {number}"

    def test_unknown_symbol_returns_none(self) -> None:
        assert define("zzz") is None
        assert define("") is None
        assert resolve("") is None


class TestNotationSkillContract:
    """المهارة: هوية BaseSkill + مُفرَدة + تدهور رشيق بلا الخدمة."""

    def test_identity_and_singleton(self) -> None:
        assert NotationSkill.name == "notation"
        assert get_notation_skill() is get_notation_skill()
        assert isinstance(get_notation_skill(), NotationSkill)

    def test_run_delegates_to_resolve(self) -> None:
        skill = get_notation_skill()
        assert skill.run(_CATASTROPHE_Q) == skill.resolve(_CATASTROPHE_Q)

    def test_local_resolution_needs_no_service(self) -> None:
        """قانون المهارات ٥: تعمل كاملةً بدون الخدمات الأخرى."""
        entry = get_notation_skill().resolve(_CATASTROPHE_Q)
        assert entry is not None and entry.symbol == "C(n,k)"

    def test_known_symbols_exposed(self) -> None:
        assert "C(n,k)" in get_notation_skill().known_symbols()

    async def test_service_failure_falls_back_locally(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """الخدمة ساقطة ⇒ الطالب يحصل على الجواب نفسه من السجلّ المحلّي."""
        skill = get_notation_skill()
        monkeypatch.setenv("NOTATION_SERVICE_URL", "http://127.0.0.1:1")
        entry = await skill.resolve_via_service(_CATASTROPHE_Q)
        assert entry is not None and entry.symbol == "C(n,k)"


class TestCognitiveResponseCombinations:
    """الجذر ٣ (ب) — قيمة enum `combinations` لم يكن لها فرع فسقطت صامتة."""

    def _response(self, monkeypatch: pytest.MonkeyPatch) -> str | None:
        """يستدعي الطبقة 4 مع تركيبة التمرين الرسمية محقونةً (لا I/O في الاختبار)."""
        combo = SimpleNamespace(
            n=11,
            k=3,
            total_combinations=165,
            same_group_favorable=14,
            groups=[
                SimpleNamespace(
                    label="كرة حمراء", count=4, favorable_combinations=4, is_possible=True
                ),
                SimpleNamespace(
                    label="كرة بيضاء", count=2, favorable_combinations=0, is_possible=False
                ),
                SimpleNamespace(
                    label="كرة خضراء", count=5, favorable_combinations=10, is_possible=True
                ),
            ],
        )

        def _fixed_combo(cls, *_args: object, **_kwargs: object) -> SimpleNamespace:
            return combo

        monkeypatch.setattr(
            ProbabilityTutorBrain, "_load_canonical_combinations", classmethod(_fixed_combo)
        )
        return ProbabilityTutorBrain._build_cognitive_response(
            concept="combinations",
            misconception="",
            question=_CATASTROPHE_Q,
            history_messages=_dialogue_history(),
        )

    def test_combinations_concept_now_answers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        text = self._response(monkeypatch)
        assert text is not None, "قيمة enum ميتة: `combinations` كانت تُرجع None صامتة"
        assert "التوافيق" in text

    def test_combinations_answer_leaks_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        text = self._response(monkeypatch)
        assert text is not None
        for number in _LEAK_NUMBERS:
            assert number not in text
