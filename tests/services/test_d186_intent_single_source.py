from __future__ import annotations

"""ISS-139 (D-186) — «الكاشفات المتعارضة»: مصدر نيّة واحد + التعريف قبل المثال.

الكارثة الحيّة (transcript BAC-2024، بعد D-185):

| الدور | ما حدث | الحكم |
|---|---|---|
| «ماذا **يقصد** بالحرف C» | ظهر **المثال وحده** بلا عنوان ولا تعريف | الطالب لم يُخبَر أن `C` = التوافيق |
| «لم افهم» | عاد النظام إلى **سؤال الألوان الأول** | تصفير الموضوع (خرق D-184) |

الجذور الأربعة — كلّها مُتحقَّقة بالتشغيل:

1. **ثلاث قوائم للنيّة التعريفية لا تتّفق**: `semantic_property` (23) و`student_state`
   (13) و`shared/notation` (27). «ماذا يقصد» عرفتها واحدة؛ و«شنو يقصد» عرفتها اثنتان
   وجهلتها الثالثة — تفرّقٌ في الاتجاهين.
2. **سُلّم التصعيد يتخطّى الرُّتبة المُسلَّمة دائماً** ⇒ سؤال تعريفي مُعاد يُجاب بالمثال
   وحده. يقع هذا **حتى مع** تصنيف نيّة صحيح، فتوحيد القوائم وحده ما كان ليكفي.
3. **`_interpret_notation` يحشو المثال داخل التعريف** ⇒ تُرى الرُّتبتان مُسلَّمتين معاً.
4. **probe الافتتاح يخطف «لم أفهم»** فيُصفّر البؤرة إلى سؤال الألوان.

وعطبان تابعان اكتُشفا بالتجريب: مطابقة «هل سُلِّمت الرُّتبة؟» تفشل لأن مُنسِّق الكتابة
يحذف مسافات ⇒ إعادة حرفية ⇒ يلتقطها حارس التكرار فيستبدلها بـ«الحل الكامل» (تسريب
165/14)؛ و`combinations` — مفهوم الكارثتين — كان **بلا رُتبة ثالثة إطلاقاً**.
"""

import pytest

from app.services.skills.pedagogical_escalation_skill import (
    L1_DEFINITION,
    EscalationInput,
    get_pedagogical_escalation_skill,
)
from app.services.skills.semantic_property_skill import get_semantic_property_skill
from app.services.skills.student_state_skill import StudentStateInput, get_student_state_skill
from shared.intent import all_intents, classify, markers_for, matches, normalize

#: كل الصيغ التي يكتب بها طالب جزائري السؤال التعريفي نفسه عن الرمز `C`.
_DEFINITION_PHRASINGS = (
    "ماذا نقصد بحرف C",  # ISS-138
    "ماذا يقصد بالحرف C",  # ISS-139 — كانت `unknown`
    "شنو يقصد بـ C",  # دارجة — كانت تجهلها notation
    "ما معنى الرمز C",
    "ما المقصود بالرمز C",
)


# ── الطبقة ١: المصدر القانوني الواحد ────────────────────────────────────────────


@pytest.mark.parametrize("question", _DEFINITION_PHRASINGS)
def test_every_phrasing_classifies_as_definition(question: str) -> None:
    """كل صيغ السؤال التعريفي تُصنَّف `definition` — لا صيغة تسقط بين القوائم."""
    assert classify(question) == "definition"


@pytest.mark.parametrize("question", _DEFINITION_PHRASINGS)
def test_all_consumers_agree_on_definitional_intent(question: str) -> None:
    """الكاشفات الثلاثة تتّفق الآن — تفرّقُها هو ISS-139 بعينه."""
    assert get_semantic_property_skill().is_definitional(question) is True
    state = get_student_state_skill().read(StudentStateInput(question=question, history=[]))
    assert state.primary_intent == "definition"


def test_compute_intent_beats_definition() -> None:
    """«احسب C(11,3)» طلب حساب لا سؤال معنى — التعريف لا يخطف دوراً حسابياً."""
    assert classify("احسب C(11,3)") == "computation"
    assert get_semantic_property_skill().is_definitional("احسب C(11,3)") is False


def test_iss128_answer_is_not_a_definition_question() -> None:
    """صفر انحدار D-155: «هل هي 14 من 165» إجابةُ طالبٍ لا سؤالٌ تعريفي."""
    assert classify("هل هي 14 من 165") is None


def test_registry_markers_are_normalized_and_nonempty() -> None:
    """كل علامة قابلة للمطابقة فعلاً (تطبيعها لا يُفرغها)."""
    for intent in all_intents():
        markers = markers_for(intent)
        assert markers, f"intent {intent!r} بلا علامات"
        assert all(normalize(m) for m in markers), f"intent {intent!r} فيه علامة تُطبَّع لفراغ"


def test_unknown_intent_raises_not_silently_false() -> None:
    """اسم نيّة مجهول خطأٌ صريح — لا `False` صامت يُخفي خطأ برمجياً."""
    with pytest.raises(KeyError):
        matches("أيّ نصّ", "no_such_intent")


# ── الطبقة ٢: التعريف قبل المثال ────────────────────────────────────────────────


def _combinations_payload(intent: str, history: list[dict[str, str]]) -> EscalationInput:
    """مدخلات السُّلّم لمفهوم التوافيق كما يبنيها المسار الحيّ."""
    out = get_semantic_property_skill().interpret("ماذا نقصد بحرف C")
    assert out is not None
    return EscalationInput(
        concept_id=out.concept_id,
        title=out.title,
        definition=out.definition,
        example=out.example,
        intent=intent,
        history=history,
    )


def test_notation_definition_does_not_embed_its_example() -> None:
    """الحقلان منفصلان — الازدواج كان يُسمّم كشف الرُّتب المُسلَّمة (الجذر ٣)."""
    out = get_semantic_property_skill().interpret("ماذا نقصد بحرف C")
    assert out is not None
    assert out.example
    assert out.example[:40] not in out.definition


def test_redefinition_is_never_answered_by_example_alone() -> None:
    """الجذر ٢: سؤال تعريفي مُعاد بعد تسليم التعريف لا يُجاب بمثالٍ عارٍ."""
    first = _combinations_payload("definition", [])
    delivered = f"## {first.title}\n\n{first.definition}"
    decision = get_pedagogical_escalation_skill().decide(
        _combinations_payload("definition", [{"role": "assistant", "content": delivered}])
    )
    assert not decision.text.startswith("## مثال ملموس")
    assert "التوافيق" in decision.text
    assert decision.rationale == "definition_before_example"


def test_first_definition_question_answers_with_the_definition() -> None:
    """أول سؤال تعريفي ⇒ التعريف نفسه (رُتبة L1)، لا قفز."""
    decision = get_pedagogical_escalation_skill().decide(_combinations_payload("definition", []))
    assert decision.strategy_level == L1_DEFINITION
    assert "التوافيق" in decision.text


def test_delivery_detection_survives_whitespace_loss() -> None:
    """مُنسِّق الكتابة يحذف مسافات؛ فشل المطابقة كان ينتهي بتسريب الحل كاملاً."""
    payload = _combinations_payload("definition", [])
    mangled = f"## {payload.title}\n\n{payload.definition}".replace(" ", "")
    decision = get_pedagogical_escalation_skill().decide(
        _combinations_payload("definition", [{"role": "assistant", "content": mangled}])
    )
    # الرُّتبة تُرى مُسلَّمة ⇒ يُضاف جديد بدل الإعادة الحرفية.
    assert decision.text != f"## {payload.title}\n\n{payload.definition}"


def test_delivered_rung_is_never_re_served() -> None:
    """`_render` لا ينزل إلى رُتبة مُسلَّمة — ذلك ما فجّر حارس التكرار فسرّب الحل."""
    payload = _combinations_payload("confusion", [])
    history = [
        {"role": "assistant", "content": f"## {payload.title}\n\n{payload.definition}"},
        {"role": "assistant", "content": f"## مثال ملموس\n\n{payload.example}"},
    ]
    decision = get_pedagogical_escalation_skill().decide(
        _combinations_payload("confusion", history)
    )
    assert payload.example[:40] not in decision.text
    for leaked in ("165", "= 14", "الحل الكامل"):
        assert leaked not in decision.text


# ── الطبقة ٣: البؤرة اللاصقة على الرمز ──────────────────────────────────────────


def test_combinations_has_a_third_rung() -> None:
    """الجذر ٤ التابع: مفهوم الكارثتين كان بلا محاكاة مصغّرة فيستنفد السُّلّم فوراً."""
    from app.services.skills.micro_simulation_skill import get_micro_simulation_skill

    skill = get_micro_simulation_skill()
    assert skill.get_micro_simulation("combinations")
    assert skill.get_apply_step("combinations")


def test_micro_simulation_leaks_no_exercise_numbers() -> None:
    """الرُّتبة الثالثة تشرح الفكرة بأرقامها الخاصّة — لا أرقام التمرين (D-113)."""
    from app.services.skills.micro_simulation_skill import get_micro_simulation_skill

    text = get_micro_simulation_skill().get_micro_simulation("combinations") or ""
    for leaked in ("165", "11", "14", "56"):
        assert leaked not in text


def test_confusion_after_a_concept_defers_the_opening_probe() -> None:
    """«لم أفهم» بعد حوارٍ مفهومي لا تُصفّر البؤرة إلى سؤال التمرين الافتتاحي."""
    from app.services.skills.probability_tutor_brain import ProbabilityTutorBrain

    history = [
        {"role": "user", "content": "ماذا نقصد بحرف C"},
        {"role": "assistant", "content": "## الرمز $C$ — التوافيق\n\nعدد طرق الاختيار."},
    ]
    assert ProbabilityTutorBrain._has_live_concept_focus("لم افهم", history) is True
    # سؤال جديد (لا حيرة) لا يُؤجّل الـ probe — الحارس مقصور على الحيرة المجرّدة.
    assert ProbabilityTutorBrain._has_live_concept_focus("ما احتمال نفس اللون", history) is False


# ── الطبقة ٤: بوّابة المصدر الواحد ──────────────────────────────────────────────


def test_single_source_gate_passes_on_the_repository() -> None:
    """البوّابة خضراء على المستودع — وإلا فالقاعدة مكتوبة وغير مفروضة."""
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(repo / "scripts/fitness/check_intent_single_source.py")],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo,
    )
    assert result.returncode == 0, result.stdout + result.stderr
