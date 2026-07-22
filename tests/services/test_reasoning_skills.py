"""D-181 — tests for the six Cognitive Reasoning Core skills + compose_reasoning.

Every skill is deterministic (no LLM in the primary path), so these run offline
with no ``OPENROUTER_API_KEY``. Covers happy paths, error/fail-open paths, the
``run()`` polymorphic dispatch, the ``instance()`` singleton, and the registry
composition unifier.
"""

from __future__ import annotations

from app.services.skills.abstraction_skill import (
    AbstractionInput,
    AbstractionSkill,
    get_abstraction_skill,
)
from app.services.skills.causal_reasoning_skill import (
    CausalReasoningInput,
    get_causal_reasoning_skill,
)
from app.services.skills.critical_thinking_skill import (
    CriticalThinkingInput,
    get_critical_thinking_skill,
)
from app.services.skills.logic_reasoning_skill import (
    LogicReasoningInput,
    get_logic_reasoning_skill,
)
from app.services.skills.mental_model_skill import (
    MentalModelInput,
    get_mental_model_skill,
)
from app.services.skills.problem_decomposition_skill import (
    ProblemDecompositionInput,
    get_problem_decomposition_skill,
)
from app.services.skills.registry import compose_reasoning


# ── LogicReasoningSkill ──────────────────────────────────────────────────────
class TestLogicReasoning:
    def test_modus_ponens_valid(self) -> None:
        out = get_logic_reasoning_skill().analyze(
            LogicReasoningInput(premises=["p -> q", "p"], conclusion="q")
        )
        assert out.valid is True
        assert out.form == "modus_ponens"
        assert out.is_fallacy is False
        assert out.counterexample is None

    def test_affirming_the_consequent_fallacy(self) -> None:
        out = get_logic_reasoning_skill().analyze(
            LogicReasoningInput(premises=["p -> q", "q"], conclusion="p")
        )
        assert out.valid is False
        assert out.form == "affirming_the_consequent"
        assert out.is_fallacy is True
        assert out.counterexample == {"p": False, "q": True}

    def test_no_premises(self) -> None:
        out = get_logic_reasoning_skill().analyze(LogicReasoningInput(premises=[], conclusion="q"))
        assert out.form == "no_premises"
        assert out.valid is False

    def test_unparseable(self) -> None:
        out = get_logic_reasoning_skill().analyze(
            LogicReasoningInput(premises=["p -> q"], conclusion="((")
        )
        assert out.form == "unparseable"
        assert out.error is not None

    def test_run_dispatch_and_singleton(self) -> None:
        skill = get_logic_reasoning_skill()
        assert skill is get_logic_reasoning_skill()
        out = skill.run(LogicReasoningInput(premises=["p"], conclusion="p"))
        assert out.form == "circular_reasoning"


# ── CriticalThinkingSkill ────────────────────────────────────────────────────
class TestCriticalThinking:
    def test_detects_bandwagon(self) -> None:
        out = get_critical_thinking_skill().analyze(
            CriticalThinkingInput(text="الجميع يعرف أن هذا صحيح")
        )
        assert "bandwagon" in out.fallacies
        assert len(out.socratic_questions) >= 3

    def test_unsupported_claim(self) -> None:
        out = get_critical_thinking_skill().analyze(
            CriticalThinkingInput(claims=["photosynthesis needs sunlight"], evidence=[])
        )
        assert out.unsupported_claims == ["photosynthesis needs sunlight"]

    def test_supported_claim(self) -> None:
        out = get_critical_thinking_skill().analyze(
            CriticalThinkingInput(
                claims=["photosynthesis needs sunlight"],
                evidence=["plants use sunlight for photosynthesis"],
            )
        )
        assert out.unsupported_claims == []

    def test_clean_text_no_fallacy(self) -> None:
        out = get_critical_thinking_skill().analyze(CriticalThinkingInput(text="نتيجة موزونة"))
        assert out.fallacies == []
        assert out.socratic_questions  # always offers probes


# ── ProblemDecompositionSkill ────────────────────────────────────────────────
class TestProblemDecomposition:
    def test_scaffold(self) -> None:
        out = get_problem_decomposition_skill().decompose(
            ProblemDecompositionInput(problem="احسب احتمال حادثة")
        )
        assert out.used_scaffold is True
        assert out.ordered_steps == ["understand", "plan", "execute", "review"]
        assert out.next_step == "understand"

    def test_custom_order(self) -> None:
        from app.services.skills.problem_decomposition_skill import SubGoalSpec

        out = get_problem_decomposition_skill().decompose(
            ProblemDecompositionInput(
                problem="p",
                subgoals=[
                    SubGoalSpec(id="b", phase="plan", depends_on=["a"]),
                    SubGoalSpec(id="a", phase="understand"),
                ],
            )
        )
        assert out.ordered_steps == ["a", "b"]
        assert out.used_scaffold is False

    def test_cycle_error(self) -> None:
        from app.services.skills.problem_decomposition_skill import SubGoalSpec

        out = get_problem_decomposition_skill().decompose(
            ProblemDecompositionInput(
                problem="p",
                subgoals=[
                    SubGoalSpec(id="a", depends_on=["b"]),
                    SubGoalSpec(id="b", depends_on=["a"]),
                ],
            )
        )
        assert out.error is not None
        assert out.ordered_steps == []


# ── CausalReasoningSkill ─────────────────────────────────────────────────────
class TestCausalReasoning:
    def test_causal_relationship(self) -> None:
        out = get_causal_reasoning_skill().analyze(
            CausalReasoningInput(edges=[["a", "b"], ["b", "c"]], classify_pair=["a", "c"])
        )
        assert out.relationship == "causal"
        assert out.has_cycle is False

    def test_confounded(self) -> None:
        out = get_causal_reasoning_skill().analyze(
            CausalReasoningInput(
                edges=[["heat", "ice_cream"], ["heat", "drowning"]],
                classify_pair=["ice_cream", "drowning"],
            )
        )
        assert out.relationship == "confounded"

    def test_counterfactual(self) -> None:
        out = get_causal_reasoning_skill().analyze(
            CausalReasoningInput(edges=[["a", "b"], ["b", "c"]], counterfactual_node="b")
        )
        assert out.counterfactual_lost_effects == ["c"]

    def test_cycle_detected(self) -> None:
        out = get_causal_reasoning_skill().analyze(
            CausalReasoningInput(edges=[["a", "b"], ["b", "a"]])
        )
        assert out.has_cycle is True

    def test_bad_edge_fail_open(self) -> None:
        out = get_causal_reasoning_skill().analyze(CausalReasoningInput(edges=[["a"]]))
        assert out.error is not None


# ── AbstractionSkill ─────────────────────────────────────────────────────────
class TestAbstraction:
    def test_generalize_instances(self) -> None:
        out = get_abstraction_skill().generalize(
            AbstractionInput(
                instances=[{"k": 1, "v": "a"}, {"k": 1, "v": "b"}],
            )
        )
        assert out.invariants == {"k": 1}
        assert out.parameters == ["v"]

    def test_sequence(self) -> None:
        out = get_abstraction_skill().generalize(AbstractionInput(sequence=[2, 4, 8, 16]))
        assert out.sequence_kind == "geometric"
        assert out.sequence_next == "32"

    def test_analogy(self) -> None:
        out = get_abstraction_skill().generalize(
            AbstractionInput(source={"a": 1, "b": 2}, target={"a": 9, "b": 8})
        )
        assert out.analogy_confidence == 1.0

    def test_empty_fail_open(self) -> None:
        out = get_abstraction_skill().generalize(AbstractionInput())
        assert out.error is not None

    def test_run_dispatch(self) -> None:
        assert isinstance(
            AbstractionSkill.instance().run(AbstractionInput(sequence=[1, 2, 3])).explanation, str
        )


# ── MentalModelSkill ─────────────────────────────────────────────────────────
class TestMentalModel:
    def test_consistent(self) -> None:
        out = get_mental_model_skill().build(
            MentalModelInput(
                name="water",
                relations=[["cloud", "has", "water"]],
                dynamics=[["heat", "evaporation"], ["evaporation", "cloud"]],
            )
        )
        assert out.consistent is True
        assert out.summary["dynamics"] == 2

    def test_contradiction(self) -> None:
        out = get_mental_model_skill().build(
            MentalModelInput(
                name="x",
                relations=[["e", "is", "p"], ["e", "is_not", "p"]],
            )
        )
        assert out.consistent is False
        assert len(out.contradictions) == 1

    def test_causal_cycle(self) -> None:
        out = get_mental_model_skill().build(
            MentalModelInput(name="x", dynamics=[["a", "b"], ["b", "a"]])
        )
        assert out.has_causal_cycle is True

    def test_bad_relation_fail_open(self) -> None:
        out = get_mental_model_skill().build(
            MentalModelInput(name="x", relations=[["only-two", "verb"]])
        )
        assert out.error is not None


# ── compose_reasoning (registry unifier) ─────────────────────────────────────
class TestComposeReasoning:
    def test_always_decomposes_any_question(self) -> None:
        comp = compose_reasoning("لماذا تتمدد المعادن بالحرارة؟")
        assert "decomposition" in comp.modes
        assert "critical_thinking" in comp.modes
        assert comp.results["decomposition"]["ordered_steps"]

    def test_activates_causal_when_edges_present(self) -> None:
        comp = compose_reasoning(
            "confounding?",
            {
                "edges": [["heat", "ice_cream"], ["heat", "drowning"]],
                "classify_pair": ["ice_cream", "drowning"],
            },
        )
        assert "causal" in comp.modes
        assert comp.results["causal"]["relationship"] == "confounded"

    def test_activates_logic_when_argument_present(self) -> None:
        comp = compose_reasoning(
            "is this valid?",
            {"premises": ["p -> q", "q"], "conclusion": "p"},
        )
        assert "logic" in comp.modes
        assert comp.results["logic"]["is_fallacy"] is True

    def test_narrative_present(self) -> None:
        comp = compose_reasoning("any question")
        assert comp.narrative
        assert comp.modes  # at least decomposition + critical_thinking
