"""
Protocol V28.0 — Text-Wall Muzzle & Pipeline Bypass tests.

يغطي:
  • companion_text (≤ 120 حرف) موجود في ImpossibleCaseOutput.
  • terminate_pipeline=True في مخرج _build_calculated_ui للحالة المستحيلة.
  • V30.0: كل مكوّن توليدي (combinations/tree) يُوقف الـ pipeline بجملة واحدة.
  • العقد المُفكَّك الصارم (visual_directives / numerical_state / pedagogical_message).
  • لا مفاتيح حساب منحلّة (tree/total_combinations/composition/groups) في props.
  • visual_pedagogy endpoint يُرجِع terminate_pipeline=True للحالة المستحيلة.
"""

from __future__ import annotations

from app.services.skills.probability_skill import (
    ImpossibleCaseOutput,
    ImpossibleNumericalState,
    ProbabilityCalculatorSkill,
    ProbabilityInput,
)

_BAC_URN = (
    "يحتوي كيس على 11 كرة: كرتان بيضاوان مرقمتان بـ 1 و 3، وأربع كرات حمراء، وخمس كرات خضراء."
)

_IMPOSSIBLE_Q = "كيفاش نسحب 3 كرات بيضاء في نفس الوقت؟"
_POSSIBLE_Q = "نسحب 3 كرات خضراء دفعة واحدة"


def _skill() -> ProbabilityCalculatorSkill:
    return ProbabilityCalculatorSkill()


# ── companion_text contract ──────────────────────────────────────────────────────


def test_impossible_case_has_companion_text() -> None:
    """V28.0: ImpossibleCaseOutput يحمل companion_text (≤ 120 حرف)."""
    out = _skill().analyze(
        ProbabilityInput(question=_IMPOSSIBLE_Q, history=[{"role": "user", "content": _BAC_URN}])
    )
    assert isinstance(out, ImpossibleCaseOutput)
    assert hasattr(out, "companion_text")
    assert isinstance(out.companion_text, str)
    assert len(out.companion_text) >= 1, "companion_text must not be empty"
    assert len(out.companion_text) <= 120, (
        f"companion_text exceeds 120-char muzzle limit: {len(out.companion_text)} chars"
    )


def test_companion_text_in_model_dump() -> None:
    """V28.0: companion_text يظهر في model_dump() — يُرسَل للواجهة ضمن الحمولة."""
    out = _skill().analyze(
        ProbabilityInput(question=_IMPOSSIBLE_Q, history=[{"role": "user", "content": _BAC_URN}])
    )
    assert isinstance(out, ImpossibleCaseOutput)
    dumped = out.model_dump()
    assert "companion_text" in dumped
    assert isinstance(dumped["companion_text"], str)
    assert len(dumped["companion_text"]) <= 120


def test_companion_text_default_is_single_sentence() -> None:
    """V28.0: القيمة الافتراضية لـ companion_text جملة واحدة قصيرة."""
    out = ImpossibleCaseOutput(
        numerical_state=ImpossibleNumericalState(
            available_items=2, requested_items=3, item_color="white"
        ),
        pedagogical_message="كيف نسحب 3 كرات ونحن نملك كرتين فقط؟",
        item_label="كرة بيضاء",
    )
    # الافتراضي يجب أن يكون جملة واحدة (لا نقطة داخلية تُشير لجملتين)
    assert len(out.companion_text) <= 120
    assert out.companion_text.strip()


# ── terminate_pipeline contract ──────────────────────────────────────────────────


def test_build_calculated_ui_terminate_pipeline_true_for_impossible() -> None:
    """V28.0 + D-116/D-123: سحب مستحيل مباشر (MODE_A) → combinations_visualizer + terminate=True.

    D-123 §6.118: عبر `_build_calculated_ui` (history=None) يُطوى السحب المستحيل داخل
    combinations_visualizer (مجموعة is_possible + pedagogical_string، بلا `C_n^k=0`)
    لا في مكوّن impossible_draw_animation مستقلّ. D-116: الكبح النصّي ساري (terminate=True).
    """
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    # سؤال مستحيل بلا إشارة حيرة → MODE_A → terminate_pipeline=True
    result = OrchestratorClient._build_calculated_ui(
        _POSSIBLE_Q.replace("خضراء", "بيضاء"),  # نسحب 3 كرات بيضاء (مستحيل: 2 فقط)
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("component") == "combinations_visualizer"
    assert result.get("routing_mode") == "MODE_A", "Direct impossible question must be MODE_A"
    assert result.get("terminate_pipeline") is True, (
        "terminate_pipeline must be True for MODE_A probability case (D-116)"
    )
    assert "companion_text" in result
    assert len(result["companion_text"]) <= 120
    # D-123: لا رياضيات منحلّة — لا مجموعة تحمل `= 0` المضلِّل.
    for group in result.get("props", {}).get("groups", []):
        ped = group.get("pedagogical_string") or ""
        assert "= 0" not in ped, f"Degenerate C_n^k=0 leaked into group: {ped}"


def test_build_calculated_ui_muzzles_all_generative_ui() -> None:
    """V30.0 (يُحدِّث V28.0): كل مكوّن توليدي يُوقف الـ pipeline بجملة واحدة.

    قانون الكبح النصي الصارم (Protocol V30.0 §4): «إذا استُدعيت أداة Generative
    UI، يجب إنهاء/تقييد مخرج LLM إلى جملة واحدة». كان V28.0 يُطبِّق هذا على
    الحالة المستحيلة فقط؛ V30.0 يعمّمه على combinations_visualizer (والشجرة)
    لإنهاء جدران النص نهائياً.
    """
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    result = OrchestratorClient._build_calculated_ui(
        _POSSIBLE_Q,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("component") == "combinations_visualizer"
    # V30.0: المكوّن البصري يُنهي المسار بجملة مرافقة واحدة (لا جدار نصّي).
    assert result.get("terminate_pipeline") is True, (
        "V30.0 mandate: generative UI must muzzle the text wall (terminate_pipeline=True)"
    )
    companion = result.get("companion_text", "")
    assert isinstance(companion, str) and 0 < len(companion) <= 120
    assert "\n" not in companion


# ── strict decoupled schema ──────────────────────────────────────────────────────


def test_impossible_case_strict_decoupled_schema() -> None:
    """V28.0: العقد المُفكَّك الصارم لـ ImpossibleCaseOutput — visual_directives /
    numerical_state / pedagogical_message — يُتحقَّق على مستوى analyze() حيث يُنتَج فعلاً.

    عبر `_build_calculated_ui` (history=None) يُطوى السحب داخل combinations (D-123)؛
    لكن مسار `analyze()` (الذي يقرأ الكيس من history) لا يزال يُنتج ImpossibleCaseOutput
    بالعقد المُفكَّك الصارم — وهو ما تحرسه هذه الاختبارات.
    """
    out = _skill().analyze(
        ProbabilityInput(question=_IMPOSSIBLE_Q, history=[{"role": "user", "content": _BAC_URN}])
    )
    assert isinstance(out, ImpossibleCaseOutput)
    # visual_directives — لا رياضيات منحلّة (fallback_math=None)
    assert out.visual_directives.animation_hint == "bag_shake"
    assert out.visual_directives.fallback_math is None, "fallback_math must be null"
    # numerical_state — العقد المُفكَّك (متاح/مطلوب/لون)
    assert out.numerical_state.available_items == 2
    assert out.numerical_state.requested_items == 3
    assert out.numerical_state.item_color == "white"
    # pedagogical_message + ui_mode
    assert out.pedagogical_message
    assert out.ui_mode == "impossible_case"


def test_impossible_case_no_degenerate_math_in_props() -> None:
    """D-123 §6.118: لا رياضيات منحلّة — السحب المستحيل لا يُنتج `C_n^k=0` المضلِّل.

    عبر `_build_calculated_ui` (history=None) يُطوى المستحيل داخل combinations؛ القاعدة
    الثابتة: أي مجموعة غير ممكنة تحمل رسالة تربوية (is_possible) بلا `= 0` مضلِّل،
    ولا حقل `fallback_math` رقمي منحلّ في أي خطوة.
    """
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    result = OrchestratorClient._build_calculated_ui(
        _IMPOSSIBLE_Q,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    props = result.get("props", {})
    # أي مجموعة (إن وُجدت) لا تحمل `= 0` المضلِّل.
    for group in props.get("groups", []):
        ped = group.get("pedagogical_string") or ""
        assert "= 0" not in ped, f"Degenerate C_n^k=0 leaked: {ped}"
    # full_exercise_story (مسار الحيرة): خطوات الحدث لا تحمل رياضيات منحلّة.
    for step in props.get("exercise_steps", []):
        vd = step.get("visual_directives") or {}
        assert vd.get("fallback_math") in (None, ""), (
            f"Degenerate fallback_math leaked into step: {vd.get('fallback_math')}"
        )


# ── visual_pedagogy HTTP endpoint contract ───────────────────────────────────────


def test_visual_pedagogy_endpoint_returns_terminate_pipeline() -> None:
    """V28.0: /api/v1/visual-pedagogy/probability يُرجِع terminate_pipeline=True للحالة المستحيلة."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routers.visual_pedagogy import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/visual-pedagogy/probability",
        json={
            "question": _IMPOSSIBLE_Q,
            "history": [{"role": "user", "content": _BAC_URN}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("ui_mode") == "impossible_case"
    assert data.get("is_impossible_case") is True
    assert data.get("terminate_pipeline") is True, (
        "terminate_pipeline must be True in HTTP response for impossible_case"
    )
    assert "companion_text" in data
    assert len(data["companion_text"]) <= 120
    # لا مفاتيح حساب منحلّة
    for forbidden in ("tree", "total_combinations", "composition", "groups"):
        assert forbidden not in data, f"Degenerate key '{forbidden}' must not appear in response"
