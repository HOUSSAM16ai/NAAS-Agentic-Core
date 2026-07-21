"""Tests for the foundational reasoning layer (app/core/foundations).

Pure stdlib + the dep-free foundations package — no fastapi/pydantic/DB. Covers
the happy path AND the error path (FoundationsError) for every domain, so the
theoretical substrate the tutor reasons from is proven correct.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from app.core.foundations import (
    algorithms,
    combinatorics,
    information_theory,
    logic,
    number_theory,
    probability,
)
from app.core.foundations.errors import FoundationsError


class TestCombinatorics:
    def test_factorial_permutations_combinations(self):
        assert combinatorics.factorial(5) == 120
        assert combinatorics.permutations(5, 2) == 20
        assert combinatorics.combinations(5, 2) == 10
        assert combinatorics.combinations(49, 6) == 13_983_816  # a lottery draw

    def test_multinomial_counts_arrangements_with_repeats(self):
        assert combinatorics.multinomial(2, 1) == 3  # AAB, ABA, BAA
        assert combinatorics.multinomial(1, 1, 1) == 6

    def test_catalan_and_stirling(self):
        assert [combinatorics.catalan(n) for n in range(5)] == [1, 1, 2, 5, 14]
        assert combinatorics.stirling_second(4, 2) == 7

    def test_k_greater_than_n_raises_not_zero(self):
        # Pedagogical rule: impossibility is an error, never a misleading 0.
        with pytest.raises(FoundationsError):
            combinatorics.combinations(2, 3)
        with pytest.raises(FoundationsError):
            combinatorics.permutations(2, 3)

    def test_negative_input_raises(self):
        with pytest.raises(FoundationsError):
            combinatorics.factorial(-1)


class TestNumberTheory:
    def test_gcd_lcm(self):
        assert number_theory.gcd(48, 36) == 12
        assert number_theory.lcm(4, 6) == 12

    @pytest.mark.parametrize("prime", [2, 3, 5, 7, 97, 7919, 1_000_003])
    def test_is_prime_true(self, prime):
        assert number_theory.is_prime(prime)

    @pytest.mark.parametrize("composite", [0, 1, 4, 9, 100, 7917])
    def test_is_prime_false(self, composite):
        assert not number_theory.is_prime(composite)

    def test_prime_factorization(self):
        assert number_theory.prime_factorization(360) == {2: 3, 3: 2, 5: 1}
        assert number_theory.prime_factorization(97) == {97: 1}

    def test_divisors_and_totient(self):
        assert number_theory.divisors(12) == [1, 2, 3, 4, 6, 12]
        assert number_theory.euler_totient(10) == 4  # 1,3,7,9

    def test_modular_arithmetic(self):
        assert number_theory.mod_pow(2, 10, 1000) == 24
        assert number_theory.mod_inverse(3, 11) == 4  # 3*4 = 12 ≡ 1 mod 11
        with pytest.raises(FoundationsError):
            number_theory.mod_inverse(2, 4)  # not coprime


class TestLogic:
    def test_connectives(self):
        assert logic.implies(True, False) is False
        assert logic.implies(False, True) is True
        assert logic.iff(True, True) is True
        assert logic.xor(True, True) is False

    def test_tautology_and_contradiction(self):
        # p ∨ ¬p is a tautology; p ∧ ¬p is a contradiction.
        assert logic.is_tautology(lambda a: a["p"] or not a["p"], ["p"])
        assert logic.is_contradiction(lambda a: a["p"] and not a["p"], ["p"])

    def test_equivalence_demorgan(self):
        # ¬(p ∧ q) ≡ ¬p ∨ ¬q
        left = lambda a: not (a["p"] and a["q"])  # noqa: E731
        right = lambda a: (not a["p"]) or (not a["q"])  # noqa: E731
        assert logic.equivalent(left, right, ["p", "q"])

    def test_entailment_modus_ponens(self):
        premises = [lambda a: logic.implies(a["p"], a["q"]), lambda a: a["p"]]
        assert logic.entails(premises, lambda a: a["q"], ["p", "q"])

    def test_truth_table_shape_and_errors(self):
        table = logic.truth_table(lambda a: a["p"], ["p"])
        assert len(table) == 2
        with pytest.raises(FoundationsError):
            logic.truth_table(lambda _a: True, [])


class TestProbability:
    def test_binomial_pmf_exact_fraction(self):
        # Two fair coin flips, exactly one head: C(2,1)·(1/2)² = 1/2.
        assert probability.binomial_pmf(1, 2, Fraction(1, 2)) == Fraction(1, 2)

    def test_binomial_cdf(self):
        assert probability.binomial_cdf(2, 2, Fraction(1, 2)) == Fraction(1)

    def test_hypergeometric_matches_urn_model(self):
        # 5 balls (2 red), draw 2, both red: C(2,2)C(3,0)/C(5,2) = 1/10.
        assert probability.hypergeometric_pmf(2, 5, 2, 2) == Fraction(1, 10)

    def test_expectation_and_variance_of_die(self):
        values = [1, 2, 3, 4, 5, 6]
        probs = [Fraction(1, 6)] * 6
        assert math.isclose(probability.expectation(values, probs), 3.5)
        assert math.isclose(probability.variance(values, probs), 35 / 12)

    def test_bayes(self):
        # 1% prevalence, 99% sensitivity, 5% false positive → ~16.7% posterior.
        post = probability.bayes_posterior(Fraction(1, 100), Fraction(99, 100), Fraction(5, 100))
        assert math.isclose(post, 0.1667, abs_tol=1e-3)

    def test_descriptive_stats(self):
        data = [2, 4, 4, 4, 5, 5, 7, 9]
        assert math.isclose(probability.mean(data), 5.0)
        assert math.isclose(probability.median(data), 4.5)
        assert math.isclose(probability.sample_stddev(data), 2.138, abs_tol=1e-3)

    def test_distribution_validation(self):
        with pytest.raises(FoundationsError):
            probability.expectation([1, 2], [Fraction(1, 2), Fraction(1, 3)])  # sums to 5/6


class TestInformationTheory:
    def test_entropy_fair_coin_is_one_bit(self):
        assert math.isclose(information_theory.entropy([0.5, 0.5]), 1.0)

    def test_entropy_certain_event_is_zero(self):
        assert math.isclose(information_theory.entropy([1.0, 0.0]), 0.0)

    def test_kl_divergence_zero_iff_equal(self):
        p = [0.5, 0.5]
        assert math.isclose(information_theory.kl_divergence(p, p), 0.0)
        assert information_theory.kl_divergence([0.9, 0.1], [0.5, 0.5]) > 0

    def test_mutual_information_independent_is_zero(self):
        # Independent joint: I(X;Y) = 0.
        joint = [[0.25, 0.25], [0.25, 0.25]]
        assert math.isclose(information_theory.mutual_information(joint), 0.0, abs_tol=1e-9)

    def test_invalid_distribution_raises(self):
        with pytest.raises(FoundationsError):
            information_theory.entropy([0.5, 0.4])  # sums to 0.9


class TestAlgorithms:
    def test_binary_search(self):
        arr = [1, 3, 5, 7, 9, 11]
        assert algorithms.binary_search(arr, 7) == 3
        assert algorithms.binary_search(arr, 8) == -1

    def test_bfs_dfs_orders(self):
        graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        assert algorithms.bfs_order(graph, "a") == ["a", "b", "c", "d"]
        assert algorithms.dfs_order(graph, "a") == ["a", "b", "d", "c"]

    def test_shortest_path_length(self):
        graph = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": ["e"], "e": []}
        assert algorithms.shortest_path_length(graph, "a", "e") == 3
        assert algorithms.shortest_path_length(graph, "e", "a") == -1
        assert algorithms.shortest_path_length(graph, "a", "a") == 0

    def test_classify_growth(self):
        sizes = [1, 2, 4, 8, 16, 32, 64]
        quadratic = [n * n for n in sizes]
        assert algorithms.classify_growth(sizes, quadratic) == "O(n^2)"
        linear = [3 * n for n in sizes]
        assert algorithms.classify_growth(sizes, linear) == "O(n)"

    def test_missing_start_node_raises(self):
        with pytest.raises(FoundationsError):
            algorithms.bfs_order({"a": []}, "z")
