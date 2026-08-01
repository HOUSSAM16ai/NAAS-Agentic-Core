"""اختبارات سجلّ المنهاج القانوني — D-193.

يغطّي العقد الذي يُرسيه `shared/curriculum/registry.py`: **تعريف المفهوم واحد**، والمُعرَّفات
مستقرّة لأنها مُخزَّنة، والتصنيف يُرجِع الغياب غياباً لا `"general"` كاذباً.

الاختبارات البنيوية هنا ليست حشواً: **ثلاثة عيوب حقيقية سقطت بها وقت البناء** —
علامات غير مُطبَّعة لا تُطابِق شيئاً أبداً، وعلامة قصيرة («شعاع») تخطف «التناقص الإشعاعي»
إلى الهندسة، وأداة التعريف تكسر كلّ علامة من كلمتين (صنف ISS-109/112/114).
"""

from __future__ import annotations

import pytest

from shared.curriculum import registry as reg
from shared.curriculum.registry import (
    CANONICAL_STREAMS,
    CANONICAL_SUBJECTS,
    CURRICULUM_REGISTRY,
    REGISTRY_VERSION,
    STREAM_COEFFICIENTS,
    CurriculumConcept,
    CurriculumError,
    classify,
    concept,
    concepts_for_stream,
    exam_weight,
    label,
    next_concepts,
    prerequisites_of,
    resolve_alias,
    subject_coefficient,
)
from shared.textnorm import normalize

ALL_IDS = frozenset(item.concept_id for item in CURRICULUM_REGISTRY)


# ── سلامة السجلّ البنيوية ────────────────────────────────────────────────────────


def test_registry_is_not_empty_and_is_versioned() -> None:
    assert CURRICULUM_REGISTRY
    assert REGISTRY_VERSION


def test_concept_ids_are_unique() -> None:
    ids = [item.concept_id for item in CURRICULUM_REGISTRY]
    assert len(ids) == len(set(ids))


def test_every_marker_is_already_normalized() -> None:
    """
    علامة غير مُطبَّعة **لا تُطابِق شيئاً أبداً** — عطبٌ صامت تماماً.

    المطابقة تجري على نصٍّ مُطبَّع، فعلامة تحمل «ة» أو «ئ» أو لكنة فرنسية تصير جسماً
    ميّتاً في السجلّ. سقطت هنا أربع علامات وقت البناء.
    """
    offenders = [
        (item.concept_id, marker)
        for item in CURRICULUM_REGISTRY
        for marker in item.markers
        if normalize(marker) != marker
    ]
    assert offenders == []


def test_no_marker_is_shared_between_concepts() -> None:
    seen: dict[str, str] = {}
    for item in CURRICULUM_REGISTRY:
        for marker in item.markers:
            assert marker not in seen, f"{marker!r}: {seen.get(marker)} vs {item.concept_id}"
            seen[marker] = item.concept_id


def test_no_marker_hides_inside_another_concepts_title() -> None:
    """
    يمنع خطف العامّ للخاصّ — والخطر مطابقةُ العلامة لنصّ **السؤال** لا لعلامةٍ أخرى.

    «شعاع» (الهندسة) كانت سلسلة فرعية داخل «الإشعاعي»، فصُنِّف «التناقص الإشعاعي»
    هندسةً — كارثة مُثبَتة وقت البناء. تصادم العلامة بالعلامة **غير** ضارّ (الأطول
    يفوز بالبناء)، أمّا اختباؤها داخل كلمةٍ من مجالٍ آخر فقاتل.

    عناوين المفاهيم أقربُ عيّنة متاحة من لغة الطالب الحقيقية.
    """
    offenders: list[str] = []
    for item in CURRICULUM_REGISTRY:
        title = normalize(item.title_ar)
        for other in CURRICULUM_REGISTRY:
            if other.concept_id == item.concept_id:
                continue
            for marker in other.markers:
                if marker in title and classify(item.title_ar) != item.concept_id:
                    offenders.append(f"{marker!r} ({other.concept_id}) hijacks {item.concept_id}")
    assert offenders == []


def test_every_prerequisite_resolves_to_a_real_concept() -> None:
    """
    `_CURRICULUM_SEQUENCE` كانت تُقدِّم الطالب إلى مفاهيم لا وجود لها في تصنيف BKT
    (`differential_equations` · `geometry` · `statistics`) — تقدّمٌ نحو مفهومٍ لا يُقاس.
    """
    dangling = [
        (item.concept_id, prereq)
        for item in CURRICULUM_REGISTRY
        for prereq in item.prerequisites
        if prereq not in ALL_IDS
    ]
    assert dangling == []


def test_prerequisite_graph_is_acyclic() -> None:
    """حلقةٌ في المتطلّبات تعني مسار تعلّم لا ينتهي."""
    colour: dict[str, int] = {}

    def visit(node: str, trail: tuple[str, ...]) -> None:
        state = colour.get(node, 0)
        assert state != 1, f"cycle through {node}: {' -> '.join([*trail, node])}"
        if state == 2:
            return
        colour[node] = 1
        for prereq in concept(node).prerequisites:
            visit(prereq, (*trail, node))
        colour[node] = 2

    for item in CURRICULUM_REGISTRY:
        visit(item.concept_id, ())


def test_micro_concepts_point_at_a_real_parent_unit() -> None:
    for item in CURRICULUM_REGISTRY:
        if item.kind == "micro":
            assert item.unit in ALL_IDS
            assert concept(item.unit).kind == "unit"


def test_units_are_their_own_unit() -> None:
    for item in CURRICULUM_REGISTRY:
        if item.kind == "unit":
            assert item.unit == item.concept_id


def test_every_concept_classifies_from_its_own_arabic_title() -> None:
    """مفهومٌ لا يُكتشَف من اسمه لن يُكتشَف من سؤال طالب."""
    unreachable = [
        item.concept_id
        for item in CURRICULUM_REGISTRY
        if classify(item.title_ar) != item.concept_id
    ]
    assert unreachable == []


def test_aliases_never_collide_with_canonical_ids() -> None:
    for item in CURRICULUM_REGISTRY:
        for alias in item.aliases:
            assert alias not in ALL_IDS


# ── المعاملات ────────────────────────────────────────────────────────────────────


def test_every_stream_has_a_coefficient_table() -> None:
    assert set(STREAM_COEFFICIENTS) == set(CANONICAL_STREAMS)


def test_every_subject_a_concept_uses_has_a_coefficient_in_each_of_its_streams() -> None:
    """تماسك: مادة يدرسها مفهومٌ في شعبةٍ يجب أن يكون لها معامل موجب هناك."""
    for item in CURRICULUM_REGISTRY:
        for stream in item.streams:
            assert subject_coefficient(item.subject, stream) > 0, (
                f"{item.concept_id}: {item.subject} has no coefficient in {stream}"
            )


def test_natural_sciences_outweighs_mathematics_in_experimental_sciences() -> None:
    """المعامل الحقيقي — وهو سبب وجوب تصنيف أسئلة العلوم بدل ابتلاعها في `general`."""
    assert subject_coefficient("natural_sciences", "experimental_sciences") == 6
    assert subject_coefficient("mathematics", "experimental_sciences") == 5


def test_subject_coefficient_rejects_unknown_stream_and_subject() -> None:
    with pytest.raises(CurriculumError, match="unknown stream"):
        subject_coefficient("mathematics", "philosophy")
    with pytest.raises(CurriculumError, match="unknown subject"):
        subject_coefficient("astrology", "mathematics")


# ── وزن الامتحان ────────────────────────────────────────────────────────────────


def test_exam_weight_is_coefficient_times_frequency() -> None:
    item = concept("immunology")
    expected = subject_coefficient("natural_sciences", "experimental_sciences") * item.bac_frequency
    assert exam_weight("immunology", "experimental_sciences") == pytest.approx(expected)


def test_exam_weight_is_zero_for_a_stream_that_does_not_study_the_concept() -> None:
    assert exam_weight("immunology", "mathematics") == 0.0


def test_exam_weight_rejects_unknown_stream() -> None:
    with pytest.raises(CurriculumError, match="unknown stream"):
        exam_weight("probability", "philosophy")


def test_concepts_for_stream_is_sorted_by_weight_descending() -> None:
    ordered = concepts_for_stream("experimental_sciences")
    weights = [exam_weight(item.concept_id, "experimental_sciences") for item in ordered]
    assert weights == sorted(weights, reverse=True)
    assert all("experimental_sciences" in item.streams for item in ordered)


def test_concepts_for_stream_rejects_unknown_stream() -> None:
    with pytest.raises(CurriculumError, match="unknown stream"):
        concepts_for_stream("philosophy")


# ── التصنيف ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        # الصنف الذي كسر النظام ثلاث مرّات: أداة التعريف تفصل كلمتَي العلامة.
        ("اشرح لي الاحتمال الشرطي", "conditional_probability"),
        ("التناقص الإشعاعي", "nuclear_decay"),
        ("المعادلات التفاضلية", "differential_equations"),
        # الرياضيات
        ("احسب تكامل الدالة f", "integration"),
        ("ما هي المتتالية الحسابية", "sequences"),
        ("الأعداد المركبة", "complex_numbers"),
        ("الدوال المركبة", "complex_numbers"),  # ISS-114
        ("جداء أرقامها معدوم", "product_zero"),
        # الفيزياء — كانت كلّها general
        ("قوانين نيوتن", "mechanics_newton"),
        ("شحن المكثفة في ثنائي القطب RC", "rc_circuit"),
        ("زمن نصف التفاعل", "chemical_kinetics"),
        # العلوم الطبيعية — كانت كلّها general
        ("ما هي المناعة", "immunology"),
        ("تركيب البروتين", "protein_synthesis"),
        ("التنفس الخلوي", "energy_metabolism"),
        # الفرنسية بلكنة وبدونها
        ("dérivée de la fonction", "derivatives"),
        ("derivee de la fonction", "derivatives"),
        ("calcul de l'intégrale", "integration"),
    ],
)
def test_classify_maps_real_student_phrasings(question: str, expected: str) -> None:
    assert classify(question) == expected


@pytest.mark.parametrize("question", ["", "   ", "السلام عليكم", "ما عاصمة الجزائر", "كيف حالك"])
def test_classify_returns_none_rather_than_a_false_general(question: str) -> None:
    """
    الغياب يُعبَّر عنه بالغياب.

    `classify_concept` القديمة كانت تُرجِع `"general"` فتُكتَب صفوف إتقان على مفهومٍ لا
    وجود له — تلويثٌ دائم لتاريخ الطالب (ISS-112).
    """
    assert classify(question) is None


def test_classify_prefers_the_more_specific_marker() -> None:
    assert classify("احتمال") == "probability"
    assert classify("احتمال شرطي") == "conditional_probability"


def test_strip_articles_leaves_short_words_alone() -> None:
    """«ال» جزءٌ أصيل من كلمات قصيرة — حذفه يشوّهها."""
    assert reg._strip_articles("الان") == "الان"
    assert reg._strip_articles("الاحتمال") == "احتمال"


# ── الحلّ والتسمية ──────────────────────────────────────────────────────────────


def test_resolve_alias_maps_the_legacy_memory_agent_id() -> None:
    """`conditional_prob` مقابل `conditional_probability` — الانقسام الذي جسره هذا السجلّ."""
    assert resolve_alias("conditional_prob") == "conditional_probability"
    assert resolve_alias("probability") == "probability"
    assert resolve_alias("nonsense") == "nonsense"


def test_concept_accepts_an_alias() -> None:
    assert concept("conditional_prob").concept_id == "conditional_probability"


def test_concept_raises_on_unknown_id() -> None:
    with pytest.raises(CurriculumError, match="unknown concept_id"):
        concept("phlogiston")


def test_label_returns_arabic_title_and_tolerates_the_unknown() -> None:
    assert label("probability") == "الاحتمالات"
    assert label("phlogiston") == "phlogiston"
    assert label("") == "المفهوم"


def test_prerequisites_and_next_concepts_are_mutually_consistent() -> None:
    for item in CURRICULUM_REGISTRY:
        for prereq in item.prerequisites:
            assert item.concept_id in next_concepts(prereq)


def test_prerequisites_of_reads_through_an_alias() -> None:
    assert prerequisites_of("conditional_prob") == ("probability",)


def test_next_concepts_of_a_leaf_is_empty() -> None:
    assert next_concepts("product_zero") == ()


# ── تحقّق العقد على البناء ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("difficulty", 1.4, "difficulty must be in"),
        ("difficulty", -0.1, "difficulty must be in"),
        ("bac_frequency", 2.0, "bac_frequency must be in"),
        ("subject", "astrology", "unknown subject"),
        ("kind", "chapter", "kind must be"),
    ],
)
def test_invalid_concept_definitions_raise(field: str, value: object, message: str) -> None:
    kwargs: dict[str, object] = {
        "concept_id": "x",
        "title_ar": "س",
        "title_fr": "x",
        "subject": "mathematics",
    }
    kwargs[field] = value
    with pytest.raises(CurriculumError, match=message):
        CurriculumConcept(**kwargs)  # type: ignore[arg-type]


def test_unknown_stream_on_a_concept_raises() -> None:
    with pytest.raises(CurriculumError, match="unknown stream"):
        CurriculumConcept(
            concept_id="x",
            title_ar="س",
            title_fr="x",
            subject="mathematics",
            streams=("philosophy",),
        )


def test_unit_defaults_to_the_concept_id() -> None:
    item = CurriculumConcept(concept_id="solo", title_ar="س", title_fr="x", subject="mathematics")
    assert item.unit == "solo"


def test_registry_is_immutable_at_the_edges() -> None:
    """السجلّ عقد لا حالة: لا يُعدَّل وقت التشغيل."""
    with pytest.raises((TypeError, AttributeError)):
        CURRICULUM_REGISTRY[0].concept_id = "hacked"  # type: ignore[misc]
    with pytest.raises(TypeError):
        STREAM_COEFFICIENTS["experimental_sciences"] = {}  # type: ignore[index]


def test_canonical_subjects_are_all_used() -> None:
    """لا مادة مُعلَنة بلا مفهوم واحد — إعلانٌ بلا مستهلك دَينٌ لا عقد."""
    used = {item.subject for item in CURRICULUM_REGISTRY}
    assert used == set(CANONICAL_SUBJECTS)
