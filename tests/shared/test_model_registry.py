"""اختبارات سجلّ النماذج — D-202.

الاختبار المركزي هنا يُعيد تمثيل ISS-079: نموذج تفكير-فقط في الصدارة. كان يمنعه تعليقٌ
في رأس ملفّ، والتعليق لم يمنع شيئاً — قرأ طالبٌ حقيقي «pepepe aaaa». هنا يصير الرفض
سلوكاً مُختبَراً.
"""

from __future__ import annotations

from datetime import date

import pytest

from shared.ai_models.model_chain import MODEL_CHAIN, PRIMARY_MODEL
from shared.ai_models.registry import (
    MODEL_REGISTRY,
    REQUIRED_FOR_PRIMARY,
    Capability,
    ModelRecord,
    ModelRegistryError,
    assert_chain_is_registered,
    assert_primary_is_eligible,
    record_for,
)


def test_every_model_in_the_chain_is_registered() -> None:
    """نموذجٌ في السلسلة بلا إدخال يعني قدرةً مجهولة على مسار إجابة الطالب."""
    for model_id in MODEL_CHAIN:
        assert record_for(model_id).model_id == model_id


def test_an_unregistered_model_raises_rather_than_being_assumed_safe() -> None:
    with pytest.raises(ModelRegistryError, match="no registry entry"):
        record_for("some/unknown-model:free")


def test_the_current_primary_is_eligible() -> None:
    assert_primary_is_eligible(PRIMARY_MODEL)


def test_the_reasoning_only_model_can_never_be_primary() -> None:
    """
    ISS-079 حرفياً: `nvidia/nemotron-3-nano-30b-a3b:free` يُرجِع `content=None` مع
    برومبت نظامٍ طويل. الرفض هنا سلوكٌ لا تعليق.
    """
    with pytest.raises(ModelRegistryError, match="reasoning-only"):
        assert_primary_is_eligible("nvidia/nemotron-3-nano-30b-a3b:free")


def test_a_model_missing_one_capability_cannot_lead() -> None:
    """
    نقصُ قدرةٍ يكفي، والرسالة **تسمّي الناقص**: «غير مؤهّل» بلا سبب لا يُعلِّم أحداً شيئاً.

    `gpt-oss-120b` غير محظور — أُزيل من الطبقة المجانية فقط — فالرفض هنا سببه نقص
    القدرة لا الحظر، وهو ما يجعل الفرع مُختبَراً فعلاً.
    """
    with pytest.raises(ModelRegistryError, match="content_stream"):
        assert_primary_is_eligible("openai/gpt-oss-120b:free")


def test_the_english_leaking_model_stays_out_of_the_chain() -> None:
    """
    ISS-107: `nemotron-3-super-120b` سرّب نصّاً إنجليزياً داخل `content`. حظرٌ كلّي —
    لا ذيل ولا حراسة.
    """
    assert "nvidia/nemotron-3-super-120b:free" not in MODEL_CHAIN
    assert record_for("nvidia/nemotron-3-super-120b:free").is_banned


def test_an_outright_banned_model_in_the_chain_fails_loudly() -> None:
    """
    الحظر الكلّي يختلف عن حظر الصدارة. الخلط بينهما هو ما يُعيد نموذجاً مسرِّباً
    إلى المسار — فيُختبَر الفرق صراحةً.
    """
    with pytest.raises(ModelRegistryError, match="banned outright"):
        assert_chain_is_registered((PRIMARY_MODEL, "nvidia/nemotron-3-super-120b:free"))


def test_a_primary_banned_model_may_still_ride_in_the_tail() -> None:
    assert "nvidia/nemotron-3-nano-30b-a3b:free" in MODEL_CHAIN
    assert_chain_is_registered(MODEL_CHAIN)


def test_a_record_without_evidence_is_rejected_at_construction() -> None:
    """سجلٌّ بلا دليل ادّعاءٌ لا معرفة."""
    with pytest.raises(ModelRegistryError, match="evidence"):
        ModelRecord(
            model_id="x/y:free",
            capabilities=frozenset(),
            verified_on=date(2026, 8, 1),
            evidence="",
        )


def test_a_record_without_an_id_is_rejected() -> None:
    with pytest.raises(ModelRegistryError, match="model_id"):
        ModelRecord(
            model_id="",
            capabilities=frozenset(),
            verified_on=date(2026, 8, 1),
            evidence="none",
        )


def test_every_record_carries_a_verification_date() -> None:
    """قدرةٌ بلا تاريخ تحقّقٍ لا تُميَّز عن قدرةٍ موعودة في بطاقة النموذج."""
    assert all(isinstance(record.verified_on, date) for record in MODEL_REGISTRY.values())


def test_a_banned_model_is_never_eligible_however_capable() -> None:
    """القدرة لا ترفع الحظر — وإلّا كان الحظر توصيةً."""
    fully_capable_but_banned = ModelRecord(
        model_id="x/y:free",
        capabilities=frozenset(Capability),
        verified_on=date(2026, 8, 1),
        evidence="hypothetical",
        banned_reason="BANNED entirely: test",
    )
    assert fully_capable_but_banned.eligible_as_primary is False


def test_the_primary_requirements_are_all_failure_derived() -> None:
    """كل شرطٍ للصدارة يقابل فشلاً حياً مُوثَّقاً — لا شرط ذوقي."""
    assert Capability.CONTENT_STREAM in REQUIRED_FOR_PRIMARY
    assert Capability.ARABIC in REQUIRED_FOR_PRIMARY
    assert Capability.LATEX in REQUIRED_FOR_PRIMARY
    assert Capability.CLEAN_FINISH in REQUIRED_FOR_PRIMARY
