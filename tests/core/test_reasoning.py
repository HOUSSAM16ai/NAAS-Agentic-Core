"""D-181 — tests for the verified reasoning substrate ``app/core/reasoning``.

Pure, dependency-free, deterministic — exercises every module (arguments, causal,
decomposition, abstraction, mental_model) including the error paths that must raise
``ReasoningError`` rather than return a misleading value.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.core.reasoning import abstraction as ab
from app.core.reasoning import arguments as arg
from app.core.reasoning import causal as ca
from app.core.reasoning import decomposition as dec
from app.core.reasoning import mental_model as mm
from app.core.reasoning.errors import ReasoningError

# ── arguments / logic ────────────────────────────────────────────────────────


class TestArguments:
    def test_parse_and_evaluate(self) -> None:
        e = arg.parse("p -> q")
        assert e.evaluate({"p": True, "q": False}) is False
        assert e.evaluate({"p": False, "q": False}) is True
        assert sorted(e.atoms()) == ["p", "q"]

    def test_parse_operators_and_aliases(self) -> None:
        assert sorted(arg.parse("a and not b").atoms()) == ["a", "b"]
        assert sorted(arg.parse("p ∧ q ∨ ~r").atoms()) == ["p", "q", "r"]
        assert isinstance(arg.parse("p <-> q"), arg.Iff)
        assert isinstance(arg.parse("(p | q) -> r"), arg.Implies)

    @pytest.mark.parametrize("bad", ["", "p &", "p q", "(p", "p ->", "&p"])
    def test_parse_errors(self, bad: str) -> None:
        with pytest.raises(ReasoningError):
            arg.parse(bad)

    def test_modus_ponens_valid(self) -> None:
        a = arg.make_argument([arg.parse("p -> q"), arg.parse("p")], arg.parse("q"))
        assert a.is_valid() is True
        assert arg.classify_argument_form(a) == "modus_ponens"
        assert a.counterexample() is None

    def test_modus_tollens_valid(self) -> None:
        a = arg.make_argument([arg.parse("p -> q"), arg.parse("~q")], arg.parse("~p"))
        assert a.is_valid() is True
        assert arg.classify_argument_form(a) == "modus_tollens"

    def test_affirming_the_consequent_is_fallacy(self) -> None:
        a = arg.make_argument([arg.parse("p -> q"), arg.parse("q")], arg.parse("p"))
        form = arg.classify_argument_form(a)
        assert form == "affirming_the_consequent"
        assert arg.is_fallacy(form) is True
        assert a.is_valid() is False
        ce = a.counterexample()
        assert ce is not None and ce["p"] is False and ce["q"] is True

    def test_denying_the_antecedent_is_fallacy(self) -> None:
        a = arg.make_argument([arg.parse("p -> q"), arg.parse("~p")], arg.parse("~q"))
        assert arg.classify_argument_form(a) == "denying_the_antecedent"
        assert a.is_valid() is False

    def test_hypothetical_and_disjunctive_syllogism(self) -> None:
        hs = arg.make_argument([arg.parse("p -> q"), arg.parse("q -> r")], arg.parse("p -> r"))
        assert arg.classify_argument_form(hs) == "hypothetical_syllogism"
        ds = arg.make_argument([arg.parse("p | q"), arg.parse("~p")], arg.parse("q"))
        assert arg.classify_argument_form(ds) == "disjunctive_syllogism"

    def test_circular_reasoning(self) -> None:
        a = arg.make_argument([arg.parse("p"), arg.parse("q")], arg.parse("p"))
        assert arg.classify_argument_form(a) == "circular_reasoning"
        assert arg.is_fallacy("circular_reasoning") is True

    def test_soundness(self) -> None:
        a = arg.make_argument([arg.parse("p -> q"), arg.parse("p")], arg.parse("q"))
        assert a.is_sound({"p": True, "q": True}) is True
        assert a.is_sound({"p": False, "q": True}) is False  # premise p false

    def test_empty_premises_errors(self) -> None:
        with pytest.raises(ReasoningError):
            arg.Argument(premises=(), conclusion=arg.Atom("p"))

    def test_atom_empty_errors(self) -> None:
        with pytest.raises(ReasoningError):
            arg.Atom("")

    def test_missing_assignment_errors(self) -> None:
        with pytest.raises(ReasoningError):
            arg.Atom("p").evaluate({})


# ── causal ───────────────────────────────────────────────────────────────────


class TestCausal:
    def test_direct_and_transitive_cause(self) -> None:
        g = ca.CausalGraph.from_edges([("a", "b"), ("b", "c")])
        assert g.is_cause_of("a", "c") is True
        assert g.is_cause_of("c", "a") is False
        assert g.descendants("a") == frozenset({"b", "c"})
        assert g.ancestors("c") == frozenset({"a", "b"})

    def test_self_cause_rejected(self) -> None:
        g = ca.CausalGraph()
        with pytest.raises(ReasoningError):
            g.add_edge("x", "x")

    def test_cycle_detection(self) -> None:
        assert ca.CausalGraph.from_edges([("a", "b"), ("b", "a")]).has_cycle() is True
        assert ca.CausalGraph.from_edges([("a", "b"), ("b", "c")]).has_cycle() is False
        with pytest.raises(ReasoningError):
            ca.CausalGraph.from_edges([("a", "b"), ("b", "a")]).require_acyclic()

    def test_confounded_is_not_causal(self) -> None:
        # heat causes both ice-cream sales and drowning; they correlate, no causation.
        g = ca.CausalGraph.from_edges([("heat", "ice_cream"), ("heat", "drowning")])
        assert g.classify_relationship("ice_cream", "drowning") == "confounded"

    def test_relationship_classifications(self) -> None:
        g = ca.CausalGraph.from_edges([("a", "b"), ("x", "y")])
        assert g.classify_relationship("a", "b") == "causal"
        assert g.classify_relationship("b", "a") == "reverse_causal"
        assert g.classify_relationship("a", "x") == "independent"
        with pytest.raises(ReasoningError):
            g.classify_relationship("a", "a")

    def test_counterfactual_chain(self) -> None:
        g = ca.CausalGraph.from_edges([("a", "b"), ("b", "c")])
        assert g.counterfactual("b") == frozenset({"c"})

    def test_counterfactual_with_alternative_path(self) -> None:
        # cancer still caused by smoking directly, so removing tar loses nothing.
        g = ca.CausalGraph.from_edges(
            [("smoking", "tar"), ("tar", "cancer"), ("smoking", "cancer")]
        )
        assert g.counterfactual("tar") == frozenset()

    def test_unknown_node_errors(self) -> None:
        g = ca.CausalGraph.from_edges([("a", "b")])
        with pytest.raises(ReasoningError):
            g.is_cause_of("a", "zzz")


# ── decomposition ────────────────────────────────────────────────────────────


class TestDecomposition:
    def test_polya_scaffold_order(self) -> None:
        d = dec.polya_scaffold("solve a probability problem")
        assert d.execution_order() == ["understand", "plan", "execute", "review"]

    def test_custom_dependency_order(self) -> None:
        subs = [
            dec.SubGoal("c", "third", "execute", ("b",)),
            dec.SubGoal("a", "first", "understand"),
            dec.SubGoal("b", "second", "plan", ("a",)),
        ]
        d = dec.decompose("p", subs)
        assert d.execution_order() == ["a", "b", "c"]

    def test_cycle_detected(self) -> None:
        subs = [
            dec.SubGoal("a", "x", "execute", ("b",)),
            dec.SubGoal("b", "y", "execute", ("a",)),
        ]
        with pytest.raises(ReasoningError):
            dec.decompose("p", subs).execution_order()

    def test_unknown_dependency_errors(self) -> None:
        with pytest.raises(ReasoningError):
            dec.decompose("p", [dec.SubGoal("a", "x", "execute", ("ghost",))])

    def test_duplicate_ids_error(self) -> None:
        with pytest.raises(ReasoningError):
            dec.decompose("p", [dec.SubGoal("a", "x"), dec.SubGoal("a", "y")])

    def test_bad_phase_errors(self) -> None:
        with pytest.raises(ReasoningError):
            dec.SubGoal("a", "x", "nonsense")

    def test_empty_problem_errors(self) -> None:
        with pytest.raises(ReasoningError):
            dec.polya_scaffold("   ")

    def test_by_phase(self) -> None:
        d = dec.polya_scaffold("p")
        grouped = d.by_phase()
        assert set(grouped) == {"understand", "plan", "execute", "review"}


# ── abstraction ──────────────────────────────────────────────────────────────


class TestAbstraction:
    def test_generalize_invariants_and_parameters(self) -> None:
        p = ab.generalize(
            [
                {"shape": "triangle", "sides": 3, "color": "red"},
                {"shape": "triangle", "sides": 3, "color": "blue"},
            ]
        )
        assert p.invariants == {"shape": "triangle", "sides": 3}
        assert p.parameters == ("color",)
        assert p.matches({"shape": "triangle", "sides": 3, "color": "green"}) is True

    def test_generalize_missing_key_is_parameter(self) -> None:
        p = ab.generalize([{"a": 1, "b": 2}, {"a": 1}])
        assert p.invariants == {"a": 1}
        assert "b" in p.parameters

    def test_generalize_empty_errors(self) -> None:
        with pytest.raises(ReasoningError):
            ab.generalize([])

    def test_sequence_arithmetic(self) -> None:
        r = ab.generalize_sequence([3, 6, 9])
        assert r.kind == "arithmetic"
        assert r.next_term == Fraction(12)

    def test_sequence_geometric(self) -> None:
        r = ab.generalize_sequence([2, 4, 8, 16])
        assert r.kind == "geometric"
        assert r.next_term == Fraction(32)

    def test_sequence_constant(self) -> None:
        assert ab.generalize_sequence([5, 5, 5]).kind == "constant"

    def test_sequence_unknown(self) -> None:
        r = ab.generalize_sequence([1, 1, 2, 3, 5])
        assert r.kind == "unknown"
        assert r.next_term is None

    def test_sequence_too_short_errors(self) -> None:
        with pytest.raises(ReasoningError):
            ab.generalize_sequence([1])

    def test_analogy(self) -> None:
        a = ab.analogy(
            {"center": "nucleus", "orbiters": "electrons", "force": "em"},
            {"center": "sun", "orbiters": "planets", "force": "gravity"},
        )
        assert a.confidence == pytest.approx(1.0)
        assert set(a.mapping) == {"center", "orbiters", "force"}

    def test_analogy_partial(self) -> None:
        a = ab.analogy({"x": 1, "y": 2}, {"x": 9, "z": 3})
        assert 0.0 < a.confidence < 1.0
        assert a.unmapped_source == ("y",)
        assert a.unmapped_target == ("z",)

    def test_analogy_empty_errors(self) -> None:
        with pytest.raises(ReasoningError):
            ab.analogy({}, {"a": 1})


# ── mental_model ─────────────────────────────────────────────────────────────


class TestMentalModel:
    def test_consistent_model(self) -> None:
        m = mm.MentalModel("water_cycle")
        m.add_relation("cloud", "has", "water")
        m.add_dynamic("heat", "evaporation")
        m.add_dynamic("evaporation", "cloud")
        report = m.check_consistency()
        assert report.consistent is True
        assert report.has_causal_cycle is False
        assert report.isolated_entities == ()

    def test_contradiction_detected(self) -> None:
        m = mm.MentalModel("x")
        m.add_relation("electron", "is", "particle")
        m.add_relation("electron", "is_not", "particle")
        report = m.check_consistency()
        assert report.consistent is False
        assert len(report.contradictions) == 1

    def test_causal_cycle_detected(self) -> None:
        m = mm.MentalModel("x")
        m.add_dynamic("a", "b")
        m.add_dynamic("b", "a")
        report = m.check_consistency()
        assert report.has_causal_cycle is True
        assert report.consistent is False

    def test_isolated_entity(self) -> None:
        m = mm.MentalModel("x")
        m.add_entity("lonely")
        m.add_relation("a", "links", "b")
        assert "lonely" in m.check_consistency().isolated_entities

    def test_summary(self) -> None:
        m = mm.MentalModel("x")
        m.add_relation("a", "r", "b")
        m.add_dynamic("a", "c")
        assert m.summary() == {"entities": 3, "relations": 1, "dynamics": 1}

    def test_empty_entity_errors(self) -> None:
        m = mm.MentalModel("x")
        with pytest.raises(ReasoningError):
            m.add_entity("  ")
