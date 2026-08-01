"""اختبارات ترتيب الاسترجاع — D-200.

الاختبار المركزي هنا يمنع **عودة صنف D-193 من باب البحث**: `LIKE '%شعاع%'` تُطابق
«الإشعاعي»، فيجد طالبُ الفيزياء درساً في الهندسة. المطابقة على حدود الكلمات تجعل ذلك
غير مُمثَّل بدل أن يكون مُرشَّحاً.
"""

from __future__ import annotations

import pytest

from shared.retrieval import (
    RankedDocument,
    RetrievalError,
    rank_documents,
    score_document,
    tokenize,
)
from shared.retrieval.ranking import MAX_TERM_CONTRIBUTION, PHRASE_BONUS, TITLE_WEIGHT

COMPLEX = RankedDocument(
    "complex", "تمرين الأعداد المركبة بكالوريا 2024", "حل المعادلة في مجموعة الاعداد المركبه"
)
DECAY = RankedDocument("decay", "التناقص الإشعاعي", "نشاط إشعاعي وزمن نصف العمر")
GEOMETRY = RankedDocument("geometry", "الهندسة في الفضاء", "شعاع الاتجاه والمستوي")
PROBABILITY = RankedDocument("probability", "الاحتمالات", "كيس فيه كرات ملونة")

CORPUS = [COMPLEX, DECAY, GEOMETRY, PROBABILITY]


# ── التقطيع ────────────────────────────────────────────────────────────────────


def test_tokenize_normalizes_arabic() -> None:
    """«الأعداد المركبة» و«الاعداد المركبه» يجب أن تُنتِجا نفس الكلمات."""
    assert tokenize("الأعداد المركبة") == tokenize("الاعداد المركبه")


def test_tokenize_drops_the_definite_article() -> None:
    """
    نفس صنف D-193: طالبٌ يكتب «احتمالات» لا يجد «الاحتمالات».

    الجذر المُعرَّف نفسه في الطرفين هو القياس الوحيد المقبول.
    """
    assert tokenize("احتمالات") == tokenize("الاحتمالات")


def test_tokenize_keeps_short_words_whose_al_is_intrinsic() -> None:
    assert "الان" in tokenize("الان نبدأ")


def test_tokenize_drops_stopwords_and_single_characters() -> None:
    tokens = tokenize("ما هي الدالة في هذا التمرين ؟ x")
    assert "ما" not in tokens
    assert "في" not in tokens
    assert "x" not in tokens
    assert "داله" in tokens


def test_tokenize_handles_french_and_latin() -> None:
    assert tokenize("Calcul de l'intégrale") == ("calcul", "integrale")


# ── العطب الذي يمنعه هذا الملفّ ─────────────────────────────────────────────────


def test_a_short_term_does_not_match_inside_a_longer_word() -> None:
    """
    «شعاع» تُطابق الهندسة فقط — لا «الإشعاعي».

    هذا بالضبط ما كان `LIKE '%شعاع%'` يفعله، وهو صنف العطب الذي كلّف D-193 اختباراً
    بنيوياً في طبقة التصنيف.
    """
    results = rank_documents("شعاع", CORPUS)
    assert [match.doc_id for match in results] == ["geometry"]


def test_the_radioactive_document_is_found_by_its_own_word() -> None:
    results = rank_documents("إشعاعي", CORPUS)
    assert [match.doc_id for match in results] == ["decay"]


def test_both_spellings_find_the_same_document() -> None:
    for query in ("احتمالات", "الاحتمالات", "الإحتمالات"):
        assert [match.doc_id for match in rank_documents(query, CORPUS)] == ["probability"]


# ── الترتيب ────────────────────────────────────────────────────────────────────


def test_a_title_match_outranks_a_body_match() -> None:
    """العنوان إشارة نيّة أقوى من ورودٍ عابر في نصّ طويل."""
    in_title = RankedDocument("t", "التكامل بالتجزئة", "نصّ آخر")
    in_body = RankedDocument("b", "درس عامّ", "نتحدّث هنا عن التكامل")
    ranked = rank_documents("التكامل", [in_body, in_title])
    assert [match.doc_id for match in ranked] == ["t", "b"]


def test_a_full_phrase_match_wins() -> None:
    exact = RankedDocument("exact", "التناقص الإشعاعي", "")
    scattered = RankedDocument("scattered", "التناقص", "الإشعاعي في مكان آخر بعيد")
    ranked = rank_documents("التناقص الإشعاعي", [scattered, exact])
    assert ranked[0].doc_id == "exact"
    assert ranked[0].phrase_hit is True


def test_documents_that_match_nothing_are_dropped() -> None:
    """
    قائمة فارغة صادقة أنفع من قائمةٍ مليئة بلا معنى.

    عرض نتيجة بدرجة صفر يقول للطالب «هذا جواب» بينما لم يُطابِق شيئاً (§0).
    """
    assert rank_documents("طوبولوجيا جبرية", CORPUS) == ()


def test_ranking_is_stable_across_runs() -> None:
    """ترتيبٌ غير مستقرّ يجعل النتيجة تتحرّك بلا سبب بين تحديثين."""
    tie_a = RankedDocument("bbb", "التكامل", "")
    tie_b = RankedDocument("aaa", "التكامل", "")
    first = [match.doc_id for match in rank_documents("التكامل", [tie_a, tie_b])]
    second = [match.doc_id for match in rank_documents("التكامل", [tie_b, tie_a])]
    assert first == second == ["aaa", "bbb"]


def test_term_repetition_is_capped() -> None:
    """بلا سقف يتصدّر مستندٌ يُكرّر كلمةً مئة مرّة على مستندٍ يشرحها فعلاً."""
    spam = RankedDocument("spam", "", " ".join(["التكامل"] * 100))
    match = score_document("التكامل", spam)
    assert match.score == pytest.approx(MAX_TERM_CONTRIBUTION * 1.0)


def test_limit_is_respected() -> None:
    docs = [RankedDocument(f"d{i}", "التكامل", "") for i in range(10)]
    assert len(rank_documents("التكامل", docs, limit=3)) == 3


def test_a_zero_limit_is_rejected() -> None:
    with pytest.raises(RetrievalError, match="limit"):
        rank_documents("التكامل", CORPUS, limit=0)


# ── الشفافية ───────────────────────────────────────────────────────────────────


def test_every_match_explains_itself() -> None:
    """
    النتيجة تحمل سببها.

    صندوقٌ أسود في البحث يعني أنّ نتيجةً سيّئة لا يمكن تشخيصها — لا من الطالب ولا من
    المُصحِّح.
    """
    match = rank_documents("الأعداد المركبة", CORPUS)[0]
    assert match.doc_id == "complex"
    assert match.title_hit is True
    assert match.phrase_hit is True
    assert set(match.matched_terms) == {"اعداد", "مركبه"}


def test_confidence_is_bounded_and_monotonic() -> None:
    weak = score_document("كرات", PROBABILITY)
    strong = score_document("الأعداد المركبة", COMPLEX)
    assert 0.0 <= weak.confidence <= 1.0
    assert 0.0 <= strong.confidence <= 1.0
    assert strong.confidence > weak.confidence


def test_title_weight_and_phrase_bonus_are_positive_constants() -> None:
    assert TITLE_WEIGHT > 1.0
    assert PHRASE_BONUS > 0.0


# ── عقد الأخطاء ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("query", ["", "   ", "؟؟؟", "!!", "-"])
def test_a_query_without_searchable_terms_raises(query: str) -> None:
    with pytest.raises(RetrievalError, match="searchable terms"):
        rank_documents(query, CORPUS)


def test_an_empty_corpus_yields_no_results() -> None:
    assert rank_documents("التكامل", []) == ()


def test_documents_with_empty_fields_do_not_crash() -> None:
    blank = RankedDocument("blank", "", "")
    assert rank_documents("التكامل", [blank]) == ()
