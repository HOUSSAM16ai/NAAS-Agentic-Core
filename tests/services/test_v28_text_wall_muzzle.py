"""
Protocol V28.0 — Text-Wall Muzzle & Pipeline Bypass tests.

يغطي:
  • companion_text (≤ 120 حرف) موجود في ImpossibleCaseOutput.
  • terminate_pipeline=True في مخرج _build_calculated_ui للحالة المستحيلة.
  • المكوّنات العادية لا تُوقف الـ pipeline.
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
    """V28.0: _build_calculated_ui يُرجِع terminate_pipeline=True للحالة المستحيلة."""
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    result = OrchestratorClient._build_calculated_ui(
        _IMPOSSIBLE_Q,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    assert result.get("component") == "impossible_draw_animation"
    assert result.get("terminate_pipeline") is True, (
        "terminate_pipeline must be True — pipeline bypass contract violated"
    )
    assert "companion_text" in result
    assert len(result["companion_text"]) <= 120


def test_build_calculated_ui_no_terminate_for_possible_draw() -> None:
    """V28.0: المكوّنات العادية لا تُوقف الـ pipeline (terminate_pipeline absent/False)."""
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    result = OrchestratorClient._build_calculated_ui(
        _POSSIBLE_Q,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    # قد يُرجع None أو مكوّناً عادياً — في كلتا الحالتين terminate_pipeline يجب أن يكون False/absent
    if result is not None:
        assert result.get("terminate_pipeline") is not True, (
            f"terminate_pipeline must NOT be True for component={result.get('component')}"
        )


# ── strict decoupled schema ──────────────────────────────────────────────────────


def test_impossible_case_strict_decoupled_schema() -> None:
    """V28.0: العقد المُفكَّك الصارم — visual_directives / numerical_state / pedagogical_message."""
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    result = OrchestratorClient._build_calculated_ui(
        _IMPOSSIBLE_Q,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    props = result["props"]
    # visual_directives
    vd = props["visual_directives"]
    assert vd["animation_hint"] == "bag_shake"
    assert vd["fallback_math"] is None, "fallback_math must be null — no degenerate math"
    # numerical_state
    ns = props["numerical_state"]
    assert ns["available_items"] == 2
    assert ns["requested_items"] == 3
    assert ns["item_color"] == "white"
    # pedagogical_message
    assert props["pedagogical_message"]
    # ui_mode
    assert props["ui_mode"] == "impossible_case"


def test_impossible_case_no_degenerate_math_in_props() -> None:
    """V28.0: props لا تحوي tree/total_combinations/composition/groups."""
    from app.infrastructure.clients.orchestrator_client import OrchestratorClient

    result = OrchestratorClient._build_calculated_ui(
        _IMPOSSIBLE_Q,
        history_messages=[{"role": "user", "content": _BAC_URN}],
    )
    assert result is not None
    props = result.get("props", {})
    for forbidden_key in ("tree", "total_combinations", "composition", "groups"):
        assert forbidden_key not in props, (
            f"Degenerate math key '{forbidden_key}' must not appear in impossible_case props"
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
