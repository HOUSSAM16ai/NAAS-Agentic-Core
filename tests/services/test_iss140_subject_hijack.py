"""ISS-140 — الموضوع لا يُختطَف: عدّاد الحيرة لا يحسب الدور الحاضر مرّتين.

**الكارثة المُثبَتة حيّاً (2026-07-30، مونوليث حقيقي + OpenRouter حقيقي عبر WebSocket، حساب
جديد بصفر حالة سابقة):** سؤال فيزياء «اشرح لي قانون أوم» تلقّى **قائمة تشخيص الاحتمالات**:

    لنحدّد أين تحديداً تعثّرت … (أ) فضاء العينة (ب) الحالات الملائمة (ج) معنى الاحتمال

وتكرّر على «اشرح لي مبدأ أرخميدس» — فليس كاشاً ولا تسرّب حالة.

**الجذر (بالتعقّب وقت التشغيل لا بالتخمين):** المونوليث يحفظ رسالة الطالب في قاعدة البيانات
**قبل** بناء الدور (§6.5 — الكاتب واحد عند مدخل الـWS)، فالتاريخ المُمرَّر إلى
``_count_probability_confusion`` يحتوي نسخةً من ``question`` نفسه. فكان سؤالٌ واحد يُعَدّ
**2**، فيجتاز شرط «الحيرة المتكررة (≥2)» في **أوّل رسالة**، فيُقسَر
``concept = full_solution`` (بعد بوّابة الموضوع التي أضفناها) ويُسحَب أي موضوع إلى عقل
الاحتمالات.

الشرط يعني «تكراراً» فعليّاً — ولا يجوز أن يستوفيه دورٌ واحد. الإصلاح يتجاوز **نسخةً واحدة**
من الدور الحاضر ويُبقي كل تكرار سابق حقيقي.
"""

from __future__ import annotations

import pytest

from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.skills.concept_diagnosis_skill import ConceptDiagnosisSkill

_count = OrchestratorClient._count_probability_confusion


# ── عدّاد الحيرة ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "question",
    [
        "اشرح لي قانون أوم",
        "اشرح لي مبدأ أرخميدس",
        "لم أفهم",
        "مش فاهم",
    ],
)
def test_current_turn_is_never_counted_twice(question: str) -> None:
    """الدور الحاضر + نسخته المحفوظة في التاريخ = **1**، لا 2."""
    history = [{"role": "user", "content": question}]
    assert _count(question, history) == _count(question, None), (
        "نسخة الدور الحاضر في التاريخ ضاعفت العدّاد — هذا جذر ISS-140"
    )


def test_a_single_confusion_turn_does_not_reach_the_repeat_threshold() -> None:
    """رسالة حيرة واحدة لا تجتاز عتبة «التكرار» (≥2) — وإلّا فقد الشرط معناه."""
    assert _count("لم أفهم", [{"role": "user", "content": "لم أفهم"}]) < 2


def test_a_genuine_repeat_still_counts_as_repeat() -> None:
    """التكرار الحقيقي يبقى محسوباً — لا نُفرِط في التصحيح فنُعطِّل مخرج الطوارئ (D-124)."""
    history = [
        {"role": "user", "content": "لم أفهم"},
        {"role": "user", "content": "لم أفهم"},
    ]
    assert _count("لم أفهم", history) >= 2


def test_a_genuine_repeat_with_different_wording_counts() -> None:
    """صيغتان مختلفتان للحيرة تكراران (D-186: علامات الحيرة من مصدر واحد)."""
    history = [
        {"role": "user", "content": "لم أفهم"},
        {"role": "user", "content": "مش فاهم"},
    ]
    assert _count("لم أفهم", history) >= 2


def test_non_confusion_question_counts_zero() -> None:
    """سؤال معرفي عادي ليس حيرةً — لا يقترب من العتبة."""
    question = "ما هي عاصمة الجزائر؟"
    assert _count(question, [{"role": "user", "content": question}]) == 0


def test_only_one_copy_of_the_current_turn_is_skipped() -> None:
    """نتجاوز نسخةً **واحدة** فقط — تكرارٌ ثالث يبقى مرئياً للعدّاد."""
    history = [
        {"role": "user", "content": "لم أفهم"},
        {"role": "user", "content": "لم أفهم"},
        {"role": "user", "content": "لم أفهم"},
    ]
    assert _count("لم أفهم", history) >= 3


def test_assistant_messages_never_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """رسائل المساعد ليست دليل حيرة من الطالب (قاعدة D-102)."""
    history = [{"role": "assistant", "content": "لم أفهم لم أفهم لم أفهم"}]
    assert _count("ما هي عاصمة الجزائر؟", history) == 0


# ── بوّابة الموضوع على المفهوم العامّ ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "question",
    ["اشرح لي قانون أوم", "اشرح لي مبدأ أرخميدس", "اشرح لي تعريف الحمض"],
)
def test_generic_explain_verb_yields_the_generic_concept(question: str) -> None:
    """`اشرح` وحده يُنتج المفهوم العامّ `full_solution` — لأنه **لا يملك الموضوع**.

    هذا توثيقٌ للسلوك الذي جعل بوّابة الموضوع ضرورية: التشخيص الحتمي لا يفحص الموضوع،
    فالحرس يجب أن يكون عند نقطة الاستخدام (`_stage_escape_hatch`).
    """
    assert ConceptDiagnosisSkill.diagnose_deterministic(question).concept == "full_solution"


@pytest.mark.parametrize(
    "question",
    ["اشرح لي قانون أوم", "اشرح لي مبدأ أرخميدس", "ما هو تعريف الحمض والأساس؟"],
)
def test_non_probability_questions_have_no_probability_context(question: str) -> None:
    """أسئلة غير الاحتمالات لا تحمل سياق احتمالات ⇒ بوّابة الموضوع تُحيّد المفهوم العامّ."""
    assert OrchestratorClient._is_prob_context(question) is False


def test_probability_questions_keep_their_context() -> None:
    """سؤال احتمالات حقيقي يبقى في سياقه — البوّابة لا تُعطّل المسار التربوي."""
    assert OrchestratorClient._is_prob_context("كيس فيه كرات، ما احتمال سحب كرة حمراء؟") is True
