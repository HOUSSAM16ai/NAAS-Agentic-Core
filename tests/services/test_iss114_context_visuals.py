"""ISS-114 (D-106) — اختبارات regression لكارثتَي التوجيه/السياق 3 و4.

كارثة 3: «اشرح لي المتغير العشوائي» بعد تمرين احتمالات كان يُولِّد شجرة نرد/عملة
عامة لأن أمثلة المساعد التوضيحية («رمي نردٍ ست وجوه») تُسمِّم `_strategy_universe`.
الإصلاح: مُشغِّلات universe من نص الطالب فقط + composition يسبق universe.

كارثة 4: «الدوال المركبة 2024» (صياغة طلابية للأعداد المركبة) كان يُرجِع تمرين
الاحتمالات + BKT يعرض numerical_functions. الإصلاح: aliases في arabic_normalize
و bkt_engine.
"""

from __future__ import annotations

from app.services.capabilities.arabic_normalize import primary_canonical_topic
from app.services.skills.bkt_engine import classify_concept
from app.services.skills.probability_skill import (
    ProbabilityCalculatorSkill,
    ProbabilityInput,
)

_BAG = "كيس فيه كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء، نسحب 3 كرات دفعة واحدة من الكيس"


def _strategy_of(out: object) -> str:
    for attr in ("strategy", "draw_mode", "ui_mode"):
        val = getattr(out, attr, None)
        if val:
            return str(val)
    return "unknown"


class TestCatastrophe3HistoryPoisonedUniverse:
    def test_assistant_dice_example_does_not_poison_universe(self) -> None:
        """مثال نرد في رسالة المساعد لا يفرض قالب النرد على كيس التمرين الحقيقي."""
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {
                "role": "assistant",
                "content": _BAG + " ... مثال توضيحي: رمي نردٍ ست وجوه، رمي عملة معدنية",
            },
        ]
        out = ProbabilityCalculatorSkill().analyze(
            ProbabilityInput(question="اشرح لي المتغير العشوائي", history=history)
        )
        # يجب أن يكون من التركيبة الحقيقية (الكيس) لا فضاء العيّنة العام.
        assert _strategy_of(out) != "universe"
        blob = out.model_dump_json() if hasattr(out, "model_dump_json") else str(out)
        # لا تسرّب لتسميات النرد/العملة العامة.
        assert "وجه" not in blob
        assert "كتابة" not in blob
        # الكيس الحقيقي حاضر (11 كرة).
        assert "كرة" in blob

    def test_direct_dice_question_still_universe(self) -> None:
        """سؤال نرد مباشر بلا تركيبة → universe يبقى يعمل (regression)."""
        out = ProbabilityCalculatorSkill().analyze(
            ProbabilityInput(question="نرمي حجر نرد ذا ست وجوه، ما احتمال الحصول على رقم زوجي؟")
        )
        assert _strategy_of(out) == "universe"

    def test_user_history_dice_still_triggers_universe(self) -> None:
        """كلمة النرد في رسالة الطالب (لا المساعد) لا تزال تُفعِّل universe."""
        out = ProbabilityCalculatorSkill().analyze(
            ProbabilityInput(
                question="احسب احتمال الرقم الزوجي",
                history=[{"role": "user", "content": "عندي حجر نرد ذو ست وجوه"}],
            )
        )
        assert _strategy_of(out) == "universe"


class TestCatastrophe4ComplexFunctionsPhrasing:
    def test_canonical_topic_resolves_complex_numbers(self) -> None:
        topic = primary_canonical_topic("اعطني تمرين الدوال المركبة لسنة 2024")
        assert topic is not None
        assert topic.canonical_id == "complex_numbers"

    def test_bkt_classifies_complex_functions(self) -> None:
        assert classify_concept("الدوال المركبة 2024") == "complex_numbers"
        assert classify_concept("اشرح الدالة المركبة") == "complex_numbers"

    def test_numerical_functions_still_resolves(self) -> None:
        """عدم كسر التصنيف الأصلي للدوال العددية."""
        topic = primary_canonical_topic("اعطني تمرين الدوال العددية 2016")
        assert topic is not None
        assert topic.canonical_id == "numerical_functions"
        assert classify_concept("الدوال العددية 2016") == "numerical_functions"
