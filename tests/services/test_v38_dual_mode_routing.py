"""
Protocol V38.0 — Dual-Mode Routing tests (مُحدَّثة بعقد D-116 §6.116).

يغطي:
  • MODE_A (سؤال مباشر): routing_mode="MODE_A".
  • MODE_B (حيرة الطالب): routing_mode="MODE_B" — لا يزال إشارة توجيه.
  • فصل القناتين: JSON (ui_component) + Markdown (narrative) لا يتلوّثان.
  • _build_calculated_ui يُرجِع routing_mode في كل مكوّن.

ملاحظة عقد D-116 (§6.116 — قاعدة ثابتة لا تُكسر): الاحتمالات = مُعلّم بصري حتمي
كامل ⇒ `terminate_pipeline=True` **دائماً** لكل مكوّنات الاحتمالات (combinations /
tree / full_exercise_story / impossible)، حتى في MODE_B. هذا يَعكِس جزء MODE_B من
D-085 للاحتمالات فقط: routing_mode=MODE_B يبقى إشارةً، لكن البصري الحتمي هو
البيداغوجيا (صفر سرد LLM — مصدر الغارباج). الحالة المستحيلة على مدخلات الكيس تُطوى
داخل combinations_visualizer (D-123): مجموعة `is_possible` + `pedagogical_string`
بلا `C_n^k=0` مضلِّل؛ المكوّن المستقل `impossible_draw_animation` يُختبَر على مستوى
`analyze()` (test_v28_text_wall_muzzle::test_impossible_case_has_companion_text).
"""

from __future__ import annotations

from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.skills.probability_skill import ProbabilityCalculatorSkill

# ── بيانات الاختبار ──────────────────────────────────────────────────────────────

_BAC_URN = (
    "يحتوي كيس على 11 كرة: كرتان بيضاوان مرقمتان بـ 1 و 3، وأربع كرات حمراء، وخمس كرات خضراء."
)

# MODE_A — أسئلة مباشرة (لا حيرة)
_DIRECT_SIMULTANEOUS = "نسحب 3 كرات خضراء دفعة واحدة"
_DIRECT_SEQUENTIAL = "نسحب كرة واحدة ثم كرة أخرى بدون إرجاع"

# MODE_B — إشارات حيرة
_CONFUSION_ARABIC = "لم أفهم كيف نحسب هذا"
_CONFUSION_DARIJA = "مفهمتش كيفاش نحسب"
_CONFUSION_FRENCH = "je ne comprends pas comment calculer"
_CONFUSION_WHY = "كيف حدث هذا؟ اشرح لي"

# الحالة المستحيلة
_IMPOSSIBLE_Q = "كيفاش نسحب 3 كرات بيضاء في نفس الوقت؟"  # MODE_B (confusion)
_IMPOSSIBLE_DIRECT = "نسحب 3 كرات بيضاء دفعة واحدة"  # MODE_A (direct)


# ── اختبارات routing_mode في _build_calculated_ui ────────────────────────────────


def test_direct_question_yields_mode_a() -> None:
    """MODE_A: سؤال مباشر → routing_mode='MODE_A'."""
    result = OrchestratorClient._build_calculated_ui(
        _DIRECT_SIMULTANEOUS,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("routing_mode") == "MODE_A", (
        f"Expected MODE_A for direct question, got {result.get('routing_mode')}"
    )


def test_direct_question_terminates_pipeline() -> None:
    """MODE_A: سؤال مباشر → terminate_pipeline=True (الكبح النصي ساري)."""
    result = OrchestratorClient._build_calculated_ui(
        _DIRECT_SIMULTANEOUS,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("terminate_pipeline") is True, (
        "MODE_A must terminate pipeline — Text-Wall Muzzle contract violated"
    )


def test_confusion_question_yields_mode_b() -> None:
    """MODE_B: سؤال حيرة → routing_mode='MODE_B'."""
    result = OrchestratorClient._build_calculated_ui(
        _CONFUSION_ARABIC,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("routing_mode") == "MODE_B", (
        f"Expected MODE_B for confusion question, got {result.get('routing_mode')}"
    )


def test_confusion_question_terminates_pipeline_d116() -> None:
    """MODE_B: سؤال حيرة → terminate_pipeline=True (D-116: الاحتمالات بصري حتمي كامل).

    عقد D-116 §6.116 (ثابت): الاحتمالات = مُعلّم بصري حتمي ⇒ terminate دائماً حتى عند
    الحيرة — البصري الحتمي هو البيداغوجيا، لا سرد LLM (مصدر الغارباج). routing_mode
    يبقى MODE_B كإشارة، لكن المسار يُكبَح نصّياً.
    """
    result = OrchestratorClient._build_calculated_ui(
        _CONFUSION_ARABIC,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("routing_mode") == "MODE_B"
    assert result.get("terminate_pipeline") is True, (
        "D-116: probability tutor is fully deterministic-visual — terminate always, even MODE_B"
    )


def test_darija_confusion_yields_mode_b() -> None:
    """MODE_B: حيرة بالدارجة (مفهمتش) → routing_mode='MODE_B' + terminate=True (D-116)."""
    result = OrchestratorClient._build_calculated_ui(
        _CONFUSION_DARIJA,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("routing_mode") == "MODE_B"
    assert result.get("terminate_pipeline") is True


def test_french_confusion_yields_mode_b() -> None:
    """MODE_B: حيرة بالفرنسية → routing_mode='MODE_B' + terminate=True (D-116)."""
    result = OrchestratorClient._build_calculated_ui(
        _CONFUSION_FRENCH,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("routing_mode") == "MODE_B"
    assert result.get("terminate_pipeline") is True


# ── اختبارات الحالة المستحيلة في MODE_A و MODE_B ─────────────────────────────────


def test_impossible_direct_mode_a_terminates() -> None:
    """MODE_A + سحب مستحيل (مباشر): يُطوى داخل combinations_visualizer + terminate=True (D-123).

    عقد D-123 §6.118: السحب المستحيل على مدخل الكيس لا يُنتج مكوّناً مستقلاً بل يُطوى
    داخل combinations_visualizer (مجموعة is_possible + pedagogical_string، بلا C_n^k=0).
    """
    result = OrchestratorClient._build_calculated_ui(
        _IMPOSSIBLE_DIRECT,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("component") == "combinations_visualizer"
    assert result.get("routing_mode") == "MODE_A"
    assert result.get("terminate_pipeline") is True, (
        "Impossible draw in MODE_A must terminate — no LLM should follow"
    )


def test_impossible_confusion_mode_b_terminates_d116() -> None:
    """MODE_B + سحب مستحيل (حيرة): full_exercise_story + terminate=True (D-116).

    «كيفاش» إشارة حيرة ⇒ routing_mode=MODE_B، لكن D-116 يكبح المسار نصّياً
    (terminate=True) — المُعلّم البصري الحتمي يشرح، لا سرد LLM.
    """
    result = OrchestratorClient._build_calculated_ui(
        _IMPOSSIBLE_Q,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("component") == "full_exercise_story"
    assert result.get("routing_mode") == "MODE_B", (
        "Confusion marker in question must trigger MODE_B even for impossible draw"
    )
    assert result.get("terminate_pipeline") is True, (
        "D-116: probability MODE_B still terminates — deterministic visual is the pedagogy"
    )


# ── اختبارات فصل القناتين (Channel Separation) ───────────────────────────────────


def test_ui_payload_is_pure_json_structure() -> None:
    """Channel 1 (UI): الحمولة هيكل JSON نظيف — لا Markdown، لا نص سردي."""
    result = OrchestratorClient._build_calculated_ui(
        _DIRECT_SIMULTANEOUS,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    # الحمولة يجب أن تحتوي على component + props + routing_mode
    assert "component" in result
    assert "props" in result
    assert "routing_mode" in result
    assert "terminate_pipeline" in result
    # props يجب أن يكون dict (JSON-serialisable structure)
    assert isinstance(result["props"], dict)
    # لا نص Markdown في props (لا ## أو ** أو \n\n)
    props_str = str(result["props"])
    assert "##" not in props_str, "UI props must not contain Markdown headers"


def test_companion_text_is_single_sentence_mode_a() -> None:
    """Channel 2 (text) في MODE_A: companion_text جملة واحدة ≤ 120 حرف."""
    result = OrchestratorClient._build_calculated_ui(
        _DIRECT_SIMULTANEOUS,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    companion = result.get("companion_text", "")
    assert isinstance(companion, str)
    assert 0 < len(companion) <= 120, (
        f"MODE_A companion_text must be ≤ 120 chars, got {len(companion)}"
    )
    assert "\n" not in companion, "companion_text must be a single line"


def test_routing_mode_present_in_all_component_types() -> None:
    """routing_mode + terminate=True في كل المكوّنات التي يُنتجها المحرّك فعلاً.

    عبر `_build_calculated_ui` (history=None، D-123): combinations_visualizer (MODE_A) +
    full_exercise_story (MODE_B حيرة) + probability_tree (سحب متسلسل صريح). كلها
    terminate_pipeline=True (D-116). `impossible_draw_animation` غير قابل للوصول هنا
    (يُختبَر على مستوى analyze()).
    """
    cases = [
        ("نسحب 3 كرات خضراء دفعة واحدة", "combinations_visualizer", "MODE_A"),
        (_CONFUSION_ARABIC, "full_exercise_story", "MODE_B"),
        ("كيفاش نسحب 3 كرات بيضاء من كيس فيه كرتان بيضاوان؟", "probability_tree", "MODE_B"),
    ]
    for question, expected_component, expected_mode in cases:
        result = OrchestratorClient._build_calculated_ui(
            question,
            history_messages=[{"role": "user", "content": _BAC_URN}],
        )
        assert result is not None, f"Expected result for: {question}"
        assert result.get("component") == expected_component, (
            f"Expected {expected_component}, got {result.get('component')}"
        )
        assert result.get("routing_mode") == expected_mode, (
            f"Expected {expected_mode}, got {result.get('routing_mode')}"
        )
        assert result.get("terminate_pipeline") is True, (
            f"D-116: all probability components terminate — {expected_component}"
        )


# ── اختبارات is_confusion (مصدر قرار MODE_B) ─────────────────────────────────────


def test_is_confusion_detects_arabic_markers() -> None:
    """is_confusion يكشف إشارات الحيرة العربية الصريحة."""
    markers = ["لم أفهم", "ما فهمت", "اشرح لي", "وضح لي", "كيف", "صعب"]
    for marker in markers:
        assert ProbabilityCalculatorSkill.is_confusion(marker), (
            f"Expected is_confusion=True for: {marker}"
        )


def test_is_confusion_detects_darija_markers() -> None:
    """is_confusion يكشف إشارات الحيرة بالدارجة."""
    assert ProbabilityCalculatorSkill.is_confusion("مفهمتش")
    assert ProbabilityCalculatorSkill.is_confusion("كيفاش")
    assert ProbabilityCalculatorSkill.is_confusion("ما فهمتش")


def test_is_confusion_detects_french_markers() -> None:
    """is_confusion يكشف إشارات الحيرة بالفرنسية."""
    assert ProbabilityCalculatorSkill.is_confusion("je ne comprends pas")
    assert ProbabilityCalculatorSkill.is_confusion("pas compris")
    assert ProbabilityCalculatorSkill.is_confusion("comment calculer")


def test_is_confusion_false_for_direct_questions() -> None:
    """is_confusion=False للأسئلة المباشرة (لا حيرة)."""
    direct = [
        "نسحب 3 كرات خضراء دفعة واحدة",
        "احسب احتمال سحب كرة حمراء",
        "ما هو فضاء العينة؟",
    ]
    for q in direct:
        assert not ProbabilityCalculatorSkill.is_confusion(q), (
            f"Expected is_confusion=False for direct question: {q}"
        )


# ── اختبار عقد V28.0 لا يزال سارياً في MODE_A ───────────────────────────────────


def test_v28_contract_still_holds_for_mode_a_impossible() -> None:
    """V28.0 لا يزال سارياً: impossible_case في MODE_A → terminate_pipeline=True + companion_text."""
    result = OrchestratorClient._build_calculated_ui(
        _IMPOSSIBLE_DIRECT,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("terminate_pipeline") is True
    companion = result.get("companion_text", "")
    assert isinstance(companion, str) and len(companion) >= 1
    assert len(companion) <= 120


def test_v30_contract_still_holds_for_mode_a_combinations() -> None:
    """V30.0 لا يزال سارياً: combinations_visualizer في MODE_A → terminate_pipeline=True."""
    result = OrchestratorClient._build_calculated_ui(
        _DIRECT_SIMULTANEOUS,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("component") == "combinations_visualizer"
    assert result.get("terminate_pipeline") is True, (
        "V30.0 mandate: combinations_visualizer in MODE_A must muzzle text wall"
    )
