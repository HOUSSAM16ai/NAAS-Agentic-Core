"""Tests for the "first roots" foundation modules (D-183).

Covers the 9 dep-free modules that complete the pre-programming substrate:
linear algebra, calculus, statistics, optimization, graph theory (Mathematics)
and data structures, formal languages, computability, complexity (Theory of
Computation). Every module is exercised on the happy path AND every
``FoundationsError`` domain guard, so the substrate the tutor reasons from is
proven correct — never a misleading value.
"""

from __future__ import annotations

import math

import pytest

from app.core.foundations import (
    calculus,
    complexity,
    computability,
    data_structures,
    formal_languages,
    graph_theory,
    linear_algebra,
    optimization,
    statistics,
)
from app.core.foundations.errors import FoundationsError


class TestLinearAlgebra:
    def test_vector_ops(self):
        assert linear_algebra.dot([1, 2, 3], [4, 5, 6]) == 32
        assert linear_algebra.vector_add([1, 2], [3, 4]) == [4, 6]
        assert linear_algebra.scale([1, 2], 3) == [3, 6]
        assert linear_algebra.norm([3, 4]) == 5.0

    def test_vector_errors(self):
        with pytest.raises(FoundationsError):
            linear_algebra.dot([1, 2], [1])
        with pytest.raises(FoundationsError):
            linear_algebra.dot([], [])
        with pytest.raises(FoundationsError):
            linear_algebra.vector_add([1], [1, 2])
        with pytest.raises(FoundationsError):
            linear_algebra.norm([])

    def test_matrix_ops(self):
        assert linear_algebra.transpose([[1, 2], [3, 4]]) == [[1, 3], [2, 4]]
        assert linear_algebra.matmul([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[19, 22], [43, 50]]
        assert linear_algebra.identity(2) == [[1.0, 0.0], [0.0, 1.0]]

    def test_matrix_errors(self):
        with pytest.raises(FoundationsError):
            linear_algebra.transpose([])
        with pytest.raises(FoundationsError):
            linear_algebra._validate_matrix([[1, 2], [3]])
        with pytest.raises(FoundationsError):
            linear_algebra.matmul([[1, 2]], [[1, 2]])  # inner dims disagree
        with pytest.raises(FoundationsError):
            linear_algebra.identity(0)
        with pytest.raises(FoundationsError):
            linear_algebra.identity(True)

    def test_determinant_and_singular(self):
        assert math.isclose(linear_algebra.determinant([[1, 2], [3, 4]]), -2.0)
        assert math.isclose(linear_algebra.determinant([[2, 0], [0, 3]]), 6.0)
        assert linear_algebra.determinant([[1, 2], [2, 4]]) == 0.0  # singular
        assert linear_algebra.is_singular([[1, 2], [2, 4]])
        assert not linear_algebra.is_singular([[1, 2], [3, 4]])
        with pytest.raises(FoundationsError):
            linear_algebra.determinant([[1, 2, 3], [4, 5, 6]])  # not square

    def test_solve_linear_system(self):
        sol = linear_algebra.solve_linear_system([[2, 1], [1, 3]], [3, 4])
        assert math.isclose(sol[0], 1.0) and math.isclose(sol[1], 1.0)
        with pytest.raises(FoundationsError):
            linear_algebra.solve_linear_system([[1, 2, 3]], [1])  # not square
        with pytest.raises(FoundationsError):
            linear_algebra.solve_linear_system([[1, 0], [0, 1]], [1])  # b wrong length
        with pytest.raises(FoundationsError):
            linear_algebra.solve_linear_system([[1, 1], [1, 1]], [2, 3])  # singular

    def test_rank(self):
        assert linear_algebra.matrix_rank([[1, 0], [0, 1]]) == 2
        assert linear_algebra.matrix_rank([[1, 2], [2, 4]]) == 1
        assert linear_algebra.matrix_rank([[0, 0], [0, 0]]) == 0
        # wide matrix: pivots exhaust rows before columns (early break)
        assert linear_algebra.matrix_rank([[1, 0, 0], [0, 1, 0]]) == 2


class TestCalculus:
    def test_derivative_and_nth(self):
        assert math.isclose(calculus.derivative(lambda x: x**2, 3), 6, abs_tol=1e-4)
        assert math.isclose(calculus.nth_derivative(lambda x: x**3, 2, 2), 12, abs_tol=1e-2)
        assert math.isclose(calculus.nth_derivative(lambda x: x**2, 1, 1), 2, abs_tol=1e-4)

    def test_derivative_errors(self):
        with pytest.raises(FoundationsError):
            calculus.derivative(lambda x: x, 1, h=0)
        with pytest.raises(FoundationsError):
            calculus.nth_derivative(lambda x: x, 1, 0)
        with pytest.raises(FoundationsError):
            calculus.nth_derivative(lambda x: x, 1, 2, h=0)

    def test_definite_integral(self):
        assert math.isclose(calculus.definite_integral(lambda x: x**2, 0, 3), 9, abs_tol=1e-6)
        assert math.isclose(calculus.definite_integral(lambda x: x**2, 3, 0), -9, abs_tol=1e-6)
        assert calculus.definite_integral(lambda x: x, 2, 2) == 0.0
        # odd interval count is bumped to even internally
        assert math.isclose(
            calculus.definite_integral(lambda _x: 1, 0, 2, intervals=3), 2, abs_tol=1e-6
        )
        with pytest.raises(FoundationsError):
            calculus.definite_integral(lambda x: x, 0, 1, intervals=0)

    def test_limit(self):
        assert math.isclose(calculus.limit(lambda x: x + 1, 2), 3, abs_tol=1e-4)
        with pytest.raises(FoundationsError):
            calculus.limit(lambda x: x, 1, h=0)
        with pytest.raises(FoundationsError):
            calculus.limit(lambda x: 1.0 if x >= 0 else -1.0, 0)  # jump discontinuity

    def test_newton_and_taylor(self):
        assert math.isclose(calculus.newton_root(lambda x: x**2 - 2, 1), math.sqrt(2), abs_tol=1e-6)
        coeffs = calculus.taylor_coefficients(lambda x: x**2, 0, 2)
        assert math.isclose(coeffs[0], 0, abs_tol=1e-6)
        assert math.isclose(coeffs[2], 1, abs_tol=1e-2)
        with pytest.raises(FoundationsError):
            calculus.newton_root(lambda x: x**2 - 2, 1, tol=0)
        with pytest.raises(FoundationsError):
            calculus.newton_root(lambda _x: 5, 1)  # derivative ~0, no root
        with pytest.raises(FoundationsError):
            calculus.newton_root(lambda x: x**2 + 1, 1, max_iter=3)  # no real root
        with pytest.raises(FoundationsError):
            calculus.taylor_coefficients(lambda x: x, 0, -1)


class TestStatistics:
    def test_covariance_correlation(self):
        assert math.isclose(statistics.correlation([1, 2, 3], [2, 4, 6]), 1.0)
        assert math.isclose(statistics.correlation([1, 2, 3], [6, 4, 2]), -1.0)
        assert statistics.covariance([1, 2, 3], [1, 2, 3]) > 0

    def test_regression(self):
        r = statistics.linear_regression([1, 2, 3, 4], [2, 4, 6, 8])
        assert math.isclose(r["slope"], 2.0)
        assert math.isclose(r["intercept"], 0.0, abs_tol=1e-9)
        assert math.isclose(r["r_squared"], 1.0)
        # y constant → r_squared 0 branch
        r2 = statistics.linear_regression([1, 2, 3], [5, 5, 5])
        assert math.isclose(r2["slope"], 0.0, abs_tol=1e-9)
        assert r2["r_squared"] == 0.0

    def test_z_score_standardize(self):
        assert math.isclose(statistics.z_score(5, [1, 2, 3, 4, 5]), 1.2649, abs_tol=1e-3)
        std = statistics.standardize([1, 2, 3])
        assert math.isclose(sum(std), 0.0, abs_tol=1e-9)

    def test_confidence_interval_and_t(self):
        lo, hi = statistics.confidence_interval_mean([1, 2, 3, 4, 5])
        assert lo < 3 < hi
        assert statistics.t_statistic([2, 4, 6], 2) > 0
        pct = statistics.percentile([1, 2, 3, 4], 50)
        assert math.isclose(pct, 2.5)
        assert statistics.percentile([7], 90) == 7.0
        assert statistics.percentile([1, 2, 3], 0) == 1.0

    def test_errors(self):
        with pytest.raises(FoundationsError):
            statistics.covariance([1], [1])
        with pytest.raises(FoundationsError):
            statistics.covariance([1, 2], [1])
        with pytest.raises(FoundationsError):
            statistics.correlation([1, 1], [2, 2])  # zero variance
        with pytest.raises(FoundationsError):
            statistics.linear_regression([1, 1], [2, 3])  # x zero variance
        with pytest.raises(FoundationsError):
            statistics.z_score(1, [3, 3])
        with pytest.raises(FoundationsError):
            statistics.standardize([3, 3])
        with pytest.raises(FoundationsError):
            statistics.confidence_interval_mean([1, 2], confidence=1.5)
        with pytest.raises(FoundationsError):
            statistics.confidence_interval_mean([1])
        with pytest.raises(FoundationsError):
            statistics.t_statistic([1], 0)
        with pytest.raises(FoundationsError):
            statistics.t_statistic([3, 3], 3)  # zero stderr
        with pytest.raises(FoundationsError):
            statistics.percentile([], 50)
        with pytest.raises(FoundationsError):
            statistics.percentile([1, 2], 150)


class TestOptimization:
    def test_gradient_descent(self):
        assert math.isclose(
            optimization.gradient_descent(lambda x: (x - 3) ** 2, 0.0), 3, abs_tol=1e-3
        )

    def test_golden_section(self):
        assert math.isclose(
            optimization.golden_section_search(lambda x: (x - 2) ** 2, -5, 5), 2, abs_tol=1e-5
        )

    def test_bisection(self):
        assert math.isclose(optimization.bisection_root(lambda x: x - 2, 0, 5), 2, abs_tol=1e-6)
        assert optimization.bisection_root(lambda x: x, 0, 5) == 0  # f(a)==0
        assert optimization.bisection_root(lambda x: x - 5, 0, 5) == 5  # f(b)==0
        # exhaust max_iter without convergence → fallthrough return (lo+hi)/2
        approx = optimization.bisection_root(lambda x: x - 2, 0, 5, max_iter=1)
        assert 0 <= approx <= 5

    def test_linear_program(self):
        lp = optimization.linear_program_2var((3, 2), [(1, 1, 4), (1, 3, 6)])
        assert lp["value"] > 0 and lp["x"] >= -1e-9 and lp["y"] >= -1e-9
        lp_min = optimization.linear_program_2var(
            (1, 1), [(-1, 0, -1), (0, -1, -1), (1, 1, 10)], maximize=False
        )
        assert math.isclose(lp_min["value"], 2.0, abs_tol=1e-6)
        # multiple feasible vertices where a later one improves the optimum
        lp2 = optimization.linear_program_2var((1, 2), [(1, 0, 4), (0, 1, 5), (1, 1, 6)])
        assert lp2["value"] > 0

    def test_errors(self):
        with pytest.raises(FoundationsError):
            optimization.gradient_descent(lambda x: x, 0, learning_rate=0)
        with pytest.raises(FoundationsError):
            optimization.gradient_descent(lambda x: x, 0, h=0)
        with pytest.raises(FoundationsError):
            optimization.golden_section_search(lambda x: x, 5, 1)
        with pytest.raises(FoundationsError):
            optimization.golden_section_search(lambda x: x, 1, 5, tol=0)
        with pytest.raises(FoundationsError):
            optimization.bisection_root(lambda x: x, 5, 1)
        with pytest.raises(FoundationsError):
            optimization.bisection_root(lambda x: x + 1, 1, 5)  # no sign change
        with pytest.raises(FoundationsError):
            optimization.linear_program_2var((1, 1), [], non_negative=False)
        with pytest.raises(FoundationsError):
            # x ≤ -1 AND x ≥ 1 — parallel, contradictory → no feasible vertex
            optimization.linear_program_2var((1, 1), [(1, 0, -1), (-1, 0, -1)], non_negative=False)


class TestGraphTheory:
    def test_components_and_connected(self):
        assert graph_theory.connected_components({"a": ["b"], "c": ["d"]}) == [
            ["a", "b"],
            ["c", "d"],
        ]
        assert graph_theory.is_connected({"a": ["b"], "b": ["c"]})
        assert not graph_theory.is_connected({"a": ["b"], "c": ["d"]})
        with pytest.raises(FoundationsError):
            graph_theory.is_connected({})

    def test_cycles(self):
        assert graph_theory.has_cycle({"a": ["b"], "b": ["c"], "c": ["a"]}, directed=False)
        assert not graph_theory.has_cycle({"a": ["b"], "b": ["a"]}, directed=False)
        assert graph_theory.has_cycle({"a": ["b"], "b": ["c"], "c": ["a"]}, directed=True)
        assert not graph_theory.has_cycle({"a": ["b"], "b": ["c"], "c": []}, directed=True)
        assert graph_theory.has_cycle({"a": ["a"]}, directed=False)  # self-loop

    def test_topological_sort(self):
        assert graph_theory.topological_sort({"a": ["b"], "b": ["c"], "c": []}) == ["a", "b", "c"]
        with pytest.raises(FoundationsError):
            graph_theory.topological_sort({"a": ["b"], "b": ["a"]})

    def test_degree_and_mst(self):
        assert graph_theory.degree_sequence({"a": ["b", "c"], "b": ["a"], "c": ["a"]}) == [2, 1, 1]
        mst = graph_theory.minimum_spanning_tree([("a", "b", 1), ("b", "c", 2), ("a", "c", 3)])
        assert len(mst) == 2
        assert sum(w for _u, _v, w in mst) == 3
        with pytest.raises(FoundationsError):
            graph_theory.minimum_spanning_tree([])
        with pytest.raises(FoundationsError):
            graph_theory.minimum_spanning_tree([("a", "b", -1)])
        with pytest.raises(FoundationsError):
            graph_theory.minimum_spanning_tree([("a", "b", 1), ("c", "d", 1)])  # disconnected

    def test_bipartite_and_tree(self):
        assert graph_theory.is_bipartite({"a": ["b"], "b": ["a"]})
        assert not graph_theory.is_bipartite({"a": ["b"], "b": ["c"], "c": ["a"]})  # odd cycle
        assert graph_theory.is_tree({"a": ["b"], "b": ["c"]})
        assert not graph_theory.is_tree({"a": ["b"], "b": ["c"], "c": ["a"]})
        assert not graph_theory.is_tree({"a": ["a"]})  # self-loop
        with pytest.raises(FoundationsError):
            graph_theory.is_tree({})


class TestDataStructures:
    def test_stack(self):
        s = data_structures.Stack([1])
        s.push(2)
        assert len(s) == 2 and s.peek() == 2 and s.pop() == 2
        assert not s.is_empty()
        s.pop()
        assert s.is_empty()
        with pytest.raises(FoundationsError):
            s.pop()
        with pytest.raises(FoundationsError):
            s.peek()

    def test_queue(self):
        q = data_structures.Queue([1])
        q.enqueue(2)
        assert q.peek() == 1 and q.dequeue() == 1 and len(q) == 1
        q.dequeue()
        assert q.is_empty()
        with pytest.raises(FoundationsError):
            q.dequeue()
        with pytest.raises(FoundationsError):
            q.peek()

    def test_min_heap(self):
        h = data_structures.MinHeap([5, 1, 3])
        h.push(0)
        assert h.peek() == 0 and h.pop() == 0 and len(h) == 3
        with pytest.raises(FoundationsError):
            data_structures.MinHeap().pop()
        with pytest.raises(FoundationsError):
            data_structures.MinHeap().peek()

    def test_linked_list(self):
        ll = data_structures.LinkedList([1, 2, 3])
        ll.append(4)
        assert ll.to_list() == [1, 2, 3, 4] and ll.head() == 1 and len(ll) == 4
        assert list(ll) == [1, 2, 3, 4]
        with pytest.raises(FoundationsError):
            data_structures.LinkedList().head()

    def test_bst(self):
        bst = data_structures.BinarySearchTree([5, 3, 8, 1, 4, 5])  # duplicate ignored
        bst.insert(9)  # traverses right past an existing right child
        assert bst.inorder() == [1, 3, 4, 5, 8, 9]
        assert bst.contains(4) and bst.contains(9) and not bst.contains(99)
        assert bst.min() == 1 and len(bst) == 6
        with pytest.raises(FoundationsError):
            data_structures.BinarySearchTree().min()


class TestFormalLanguages:
    def test_dfa(self):
        dfa = formal_languages.DFA(
            states=frozenset({"q0", "q1"}),
            alphabet=frozenset({"0", "1"}),
            transitions={
                ("q0", "1"): "q1",
                ("q1", "1"): "q0",
                ("q0", "0"): "q0",
                ("q1", "0"): "q1",
            },
            start="q0",
            accept=frozenset({"q1"}),
        )
        assert dfa.accepts("1") and not dfa.accepts("11")
        assert not dfa.accepts("")  # start not accepting
        with pytest.raises(FoundationsError):
            dfa.accepts("2")  # symbol not in alphabet

    def test_dfa_construction_errors(self):
        with pytest.raises(FoundationsError):
            formal_languages.DFA(frozenset({"q0"}), frozenset({"a"}), {}, "bad", frozenset())
        with pytest.raises(FoundationsError):
            formal_languages.DFA(frozenset({"q0"}), frozenset({"a"}), {}, "q0", frozenset({"z"}))
        with pytest.raises(FoundationsError):
            formal_languages.DFA(
                frozenset({"q0"}), frozenset({"a"}), {("q0", "a"): "z"}, "q0", frozenset()
            )
        with pytest.raises(FoundationsError):
            formal_languages.DFA(
                frozenset({"q0"}), frozenset({"a"}), {("q0", "b"): "q0"}, "q0", frozenset()
            )

    def test_dfa_missing_transition_rejects(self):
        dfa = formal_languages.DFA(
            frozenset({"q0"}), frozenset({"a", "b"}), {("q0", "a"): "q0"}, "q0", frozenset({"q0"})
        )
        assert not dfa.accepts("b")  # missing transition → reject

    def test_regex(self):
        assert formal_languages.matches_regex("a(b|c)*d", "abccbd")
        assert formal_languages.matches_regex("a(b|c)*d", "ad")
        assert formal_languages.matches_regex("a.c", "axc")  # dot wildcard
        # star over an empty-matchable alternation (exercises the empty-match guard)
        assert formal_languages.matches_regex("(a|)*b", "aab")
        assert formal_languages.matches_regex("(a|)*b", "b")
        assert not formal_languages.matches_regex("ab", "abc")
        assert not formal_languages.matches_regex("abc", "ab")
        with pytest.raises(FoundationsError):
            formal_languages.matches_regex("a(b", "ab")  # unbalanced (
        with pytest.raises(FoundationsError):
            formal_languages.matches_regex("ab)", "ab")  # unbalanced )

    def test_balanced(self):
        assert formal_languages.is_balanced("([]{})")
        assert formal_languages.is_balanced("no brackets here")
        assert not formal_languages.is_balanced("([)]")
        assert not formal_languages.is_balanced("(")
        assert not formal_languages.is_balanced(")")
        with pytest.raises(FoundationsError):
            formal_languages.is_balanced("x", pairs="(")

    def test_derives(self):
        grammar = {"S": ["aSb", ""]}
        assert formal_languages.derives(grammar, "S", "aabb")
        assert formal_languages.derives(grammar, "S", "")
        assert not formal_languages.derives(grammar, "S", "abab")
        with pytest.raises(FoundationsError):
            formal_languages.derives(grammar, "X", "a")


class TestComputability:
    def test_ackermann(self):
        assert computability.ackermann(0, 0) == 1
        assert computability.ackermann(2, 2) == 7
        assert computability.ackermann(3, 3) == 61
        with pytest.raises(FoundationsError):
            computability.ackermann(-1, 0)
        with pytest.raises(FoundationsError):
            computability.ackermann(True, 0)
        with pytest.raises(FoundationsError):
            computability.ackermann(4, 4)  # refused — unbounded

    def test_decidable_by_table(self):
        assert computability.is_decidable_by_table(lambda x: x > 0, [1, 2, 3])
        with pytest.raises(FoundationsError):
            computability.is_decidable_by_table(lambda x: x, [])
        with pytest.raises(FoundationsError):
            computability.is_decidable_by_table(lambda x: x, [1, 2])  # non-bool

    def test_reduction(self):
        # x is even ⇔ (x+1) is odd — a valid reduction over a finite sample
        assert computability.many_one_reduction(
            lambda x: x + 1, [0, 1, 2, 3], lambda y: y % 2 == 1, lambda x: x % 2 == 0
        )
        assert not computability.many_one_reduction(
            lambda x: x, [0, 1], lambda y: y % 2 == 1, lambda x: x % 2 == 0
        )
        with pytest.raises(FoundationsError):
            computability.many_one_reduction(lambda x: x, [], lambda _y: True, lambda _x: True)

    def test_documented_limits(self):
        assert not computability.HALTING_PROBLEM["decidable"]
        assert computability.busy_beaver(4) == 13
        with pytest.raises(FoundationsError):
            computability.busy_beaver(5)  # uncomputed
        with pytest.raises(FoundationsError):
            computability.busy_beaver(-1)


class TestComplexity:
    def test_compare_and_dominate(self):
        assert complexity.compare_growth("O(n)", "O(n^2)") == -1
        assert complexity.compare_growth("O(n)", "O(n)") == 0
        assert complexity.compare_growth("O(2^n)", "O(n)") == 1
        assert complexity.dominates("O(2^n)", "O(n^3)")
        assert not complexity.dominates("O(1)", "O(n)")

    def test_is_polynomial(self):
        assert complexity.is_polynomial("O(n log n)")
        assert not complexity.is_polynomial("O(2^n)")
        assert not complexity.is_polynomial("O(n!)")

    def test_class_info_and_catalogue(self):
        assert complexity.class_info("P")["tractable"] is True
        assert complexity.class_info("NP")["tractable"] is None
        assert "SAT" in complexity.NP_COMPLETE_EXAMPLES
        assert complexity.P_VS_NP["status"] == "open"

    def test_errors(self):
        with pytest.raises(FoundationsError):
            complexity.compare_growth("O(n)", "bogus")
        with pytest.raises(FoundationsError):
            complexity.is_polynomial("bogus")
        with pytest.raises(FoundationsError):
            complexity.class_info("BQP")
